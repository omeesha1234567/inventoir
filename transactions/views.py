import json
import logging

from decimal import Decimal, InvalidOperation
from datetime import datetime, time

from django.db import transaction
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.mixins import CompanyAccessMixin, CompanyAdminRequiredMixin, CoordinatorOrAdminMixin
from accounts.tenant import company_for_request, scoped_queryset, tenant_guard_json
from accounts.utils import (
    assign_company,
    filter_by_company,
    get_user_company,
    set_audit_user,
)
from companies.archive_views import ArchivableDeleteView
from companies.base import archive_instance

from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin, UpdateView, DeleteView
from openpyxl import Workbook

from invoice.models import Invoice, InvoiceItem
from store.models import Item, Category
from accounts.models import Customer, Vendor
from .models import (
    PAYMENT_MODE_CHOICES,
    Sale,
    Purchase,
    SaleDetail,
    PurchaseItem,
    PurchasePayment,
    SalePayment,
)
from invoice.services import (
    create_invoice_items_from_sale,
    sync_invoice_from_sale,
)
from .forms import PurchaseForm

logger = logging.getLogger(__name__)


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def resolve_request_company(request):
    company = get_user_company(request.user)
    if company is None and request.user.is_superuser:
        from accounts.utils import get_default_company
        company = get_default_company()
    return company



def split_customer_name(customer_name):
    customer_name = normalize_text(customer_name)
    if not customer_name:
        return "", ""

    name_parts = customer_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    return first_name, last_name


@login_required
def get_customer_details(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405
        )

    guard = tenant_guard_json(request)
    if guard is not None:
        return guard

    try:
        customer_name = request.POST.get("customer_name", "").strip()
        first_name, last_name = split_customer_name(customer_name)

        if not first_name:
            return JsonResponse(
                {
                    "status": "success",
                    "found": False,
                    "phone": "",
                    "address": "",
                    "gst_number": "",
                }
            )

        customer_qs = scoped_queryset(Customer, request.user).filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        )
        customer = customer_qs.first()

        if customer is None:
            return JsonResponse(
                {
                    "status": "success",
                    "found": False,
                    "phone": "",
                    "address": "",
                    "gst_number": "",
                }
            )

        return JsonResponse(
            {
                "status": "success",
                "found": True,
                "phone": customer.phone or "",
                "address": customer.address or "",
                "gst_number": customer.gst_number or "",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching customer details: {e}")
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500
        )


@login_required
def get_vendor_details(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405
        )

    guard = tenant_guard_json(request)
    if guard is not None:
        return guard

    try:
        vendor_name = normalize_text(request.POST.get("vendor_name", ""))

        if not vendor_name:
            return JsonResponse(
                {
                    "status": "success",
                    "found": False,
                    "phone_number": "",
                    "email": "",
                    "gst_number": "",
                    "address": ""
                }
            )

        vendor = scoped_queryset(Vendor, request.user).filter(
            name__iexact=vendor_name,
        ).first()

        if vendor is None:
            return JsonResponse(
                {
                    "status": "success",
                    "found": False,
                    "phone_number": "",
                    "email": "",
                    "gst_number": "",
                    "address": ""
                }
            )

        return JsonResponse(
            {
                "status": "success",
                "found": True,
                "phone_number": str(vendor.phone_number) if vendor.phone_number else "",
                "email": vendor.email or "",
                "gst_number": vendor.gst_number or "",
                "address": vendor.address or ""
            }
        )

    except Exception as e:
        logger.error(f"Error fetching vendor details: {e}")
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500
        )

@login_required
def get_item_details(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405,
        )

    guard = tenant_guard_json(request)
    if guard is not None:
        return guard

    item_name = normalize_text(request.POST.get("item_name", ""))

    item = scoped_queryset(Item, request.user).filter(
        name__iexact=item_name
    ).first()

    if item is None:
        return JsonResponse(
            {
                "status": "success",
                "found": False,
            }
        )

    return JsonResponse(
        {
            "status": "success",
            "found": True,
            "description": item.description,
            "category": item.category.name if item.category else "",
            "price": str(item.price),
            "gst": item.gst_percentage,
            "hsn_code": item.hsn_code or "",
        }
    )

@login_required
def export_sales_to_excel(request):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Sales'

    columns = [
        'ID', 'Date', 'Customer', 'Sub Total',
        'Grand Total', 'Tax Amount', 'Tax Percentage',
        'Amount Paid', 'Amount Change'
    ]
    worksheet.append(columns)

    sales = filter_by_company(Sale.objects.all(), request.user)

    for sale in sales:
        if sale.date_added.tzinfo is not None:
            date_added = sale.date_added.replace(tzinfo=None)
        else:
            date_added = sale.date_added

        worksheet.append([
            sale.id,
            date_added,
            sale.customer.phone,
            sale.sub_total,
            sale.grand_total,
            sale.tax_amount,
            sale.tax_percentage,
            sale.amount_paid,
            sale.amount_change
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=sales.xlsx'
    workbook.save(response)

    return response


@login_required
def export_purchases_to_excel(request):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Purchases'

    columns = [
        'ID', 'Vendor', 'Description', 'Order Date',
        'Delivery Date', 'Items Count', 'Delivery Status',
        'Amount Paid', 'Remaining Amount', 'Total Value'
    ]
    worksheet.append(columns)

    purchases = filter_by_company(Purchase.objects.all(), request.user)

    for purchase in purchases:
        order_date = purchase.order_date
        if order_date and order_date.tzinfo is not None:
            order_date = order_date.replace(tzinfo=None)

        worksheet.append([
            purchase.id,
            purchase.vendor.name,
            purchase.description,
            order_date,
            purchase.delivery_date,
            purchase.items_count,
            purchase.get_delivery_status_display(),
            purchase.amount_paid,
            purchase.remaining_amount,
            purchase.total_value
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=purchases.xlsx'
    workbook.save(response)

    return response


from django.db.models import Q

class SaleListView(CompanyAccessMixin, ListView):
    model = Sale
    template_name = "transactions/sales_list.html"
    context_object_name = "sales"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("customer")
            .order_by("-date_added", "-id")
        )

        search = self.request.GET.get("search", "").strip()
        from_date = self.request.GET.get("from_date", "").strip()
        to_date = self.request.GET.get("to_date", "").strip()

        if search:
            queryset = queryset.filter(
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__phone__icontains=search) |
                Q(id__icontains=search) |
                Q(customer_gst_number__icontains=search)
            )
        if from_date:
            queryset = queryset.filter(date_added__date__gte=from_date)

        if to_date:
            queryset = queryset.filter(date_added__date__lte=to_date)

        return queryset


class SaleDetailView(CompanyAccessMixin, DetailView):
    model = Sale
    template_name = "transactions/saledetail.html"
    context_object_name = "sale"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.sync_payment_state(save=True)
        context["sale_items"] = self.object.saledetail_set.select_related("item").all()
        context["payment_records"] = self.object.payments.filter(
            is_archived=False,
        ).order_by('-paid_on', '-id')
        context["payment_mode_choices"] = PAYMENT_MODE_CHOICES
        invoice = getattr(self.object, 'invoice', None)
        context["invoice"] = invoice
        return context


@login_required
def SaleCreateView(request):
    company = resolve_request_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('owner-login')
    context = {
        'active_icon': 'sales',
        'customers': scoped_queryset(Customer, request.user).order_by(
            'first_name', 'last_name',
        ),
        'items': scoped_queryset(Item, request.user).order_by('name'),
    }

    if request.method == "POST" and is_ajax(request=request):
        try:
            data = json.loads(request.body)

            required_fields = ["customer_name", "amount_paid", "items"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            customer_name = normalize_text(data.get("customer_name", ""))
            phone = normalize_text(data.get("phone", ""))
            address = str(data.get("address", "")).strip()
            customer_gst = normalize_text(data.get("customer_gst_number", ""))

            if not customer_name:
                raise ValueError("Customer name is required")

            first_name, last_name = split_customer_name(customer_name)

            company = company_for_request(request)
            if company is None and not request.user.is_superuser:
                raise ValueError("Company context is required to create a sale")

            customer_instance = scoped_queryset(Customer, request.user).filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
            ).first()

            if customer_instance is None:
                customer_instance = Customer.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    address=address,
                    gst_number=customer_gst or None,
                    company=company,
                    created_by=request.user,
                    updated_by=request.user,
                )
            else:
                customer_instance.phone = phone
                customer_instance.address = address
                if customer_gst:
                    customer_instance.gst_number = customer_gst
                customer_instance.save()

            if not customer_gst and customer_instance.gst_number:
                customer_gst = customer_instance.gst_number.strip()

            items = data.get("items")
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError("At least one item is required")

            amount_paid_raw = data.get("amount_paid", 0)
            try:
                initial_amount_paid = Decimal(str(amount_paid_raw or 0))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("Invalid amount paid")
            if initial_amount_paid < 0:
                raise ValueError("Amount paid cannot be negative")

            grand_total = Decimal("0.00")

            with transaction.atomic():
                new_sale = Sale.objects.create(
                    customer=customer_instance,
                    company=company,
                    customer_gst_number=customer_gst or 'NA',
                    sub_total=0,
                    grand_total=0,
                    tax_amount=0,
                    tax_percentage=0,
                    amount_paid=0,
                    amount_change=0,
                    created_by=request.user,
                    updated_by=request.user,
                )

                for item in items:
                    if "id" not in item or "quantity" not in item:
                        raise ValueError("Item is missing required fields")

                    item_qs = scoped_queryset(
                        Item, request.user,
                    ).select_for_update()
                    item_instance = item_qs.get(id=int(item['id']))

                    quantity = int(item.get("quantity", 0))
                    margin = Decimal(str(item.get("margin", 0)))

                    gst_percentage = Decimal(
                        str(item.get("gst_percentage", item_instance.gst_percentage))
                    )

                    original_price = Decimal(str(item_instance.price))

                    if quantity <= 0:
                        raise ValueError(
                            f"Quantity should be greater than 0 for item: {item_instance.name}"
                        )

                    if margin < 0:
                        raise ValueError(
                            f"Margin cannot be negative for item: {item_instance.name}"
                        )

                    if item_instance.quantity <= 0:
                        raise ValueError(f"Item is out of stock: {item_instance.name}")

                    if item_instance.quantity < quantity:
                        raise ValueError(f"Not enough stock for item: {item_instance.name}")

                    quantity_decimal = Decimal(str(quantity))

                    unit_base = original_price + margin

                    gst_amount = unit_base * (
                        gst_percentage / Decimal("100")
                    )

                    unit_total = unit_base + gst_amount

                    total_item = unit_total * quantity_decimal

                    total_item = total_item.quantize(
                        Decimal("0.01")
                    )

                    grand_total += total_item

                    SaleDetail.objects.create(
                        sale=new_sale,
                        item=item_instance,
                        company=company,
                        price=original_price,
                        quantity=quantity,
                        total_detail=total_item,
                        gst_percentage=float(gst_percentage),
                    )

                    item_instance.quantity -= quantity
                    item_instance.save()

                new_sale.sub_total = grand_total.quantize(
                    Decimal("0.01")
                )
                new_sale.grand_total = grand_total.quantize(
                    Decimal("0.01")
                )
                new_sale.save()

                if initial_amount_paid > 0:
                    if initial_amount_paid > new_sale.grand_total:
                        raise ValueError(
                            "Amount paid cannot exceed grand total"
                        )
                    SalePayment.objects.create(
                        sale=new_sale,
                        company=company,
                        amount=initial_amount_paid,
                        payment_mode=data.get('payment_mode', 'CASH'),
                        note='Initial payment',
                        created_by=request.user,
                        updated_by=request.user,
                    )


                new_sale.sync_payment_state(save=True)

                invoice_obj, created = Invoice.objects.get_or_create(
                    sale=new_sale,
                    defaults={
                        'shipping': 0,
                        'company': company,
                        'created_by': request.user,
                        'updated_by': request.user,
                    },
                )

                create_invoice_items_from_sale(invoice_obj, new_sale, company)
                sync_invoice_from_sale(invoice_obj, save=True)
                invoice_obj.refresh_from_db()

            download_url = reverse(
                'invoice-pdf',
                kwargs={'slug': invoice_obj.slug},
            )
            return JsonResponse(
                {
                    "status": "success",
                    "message": "Sale created successfully!",
                    "redirect": reverse("saleslist"),
                    "download_url": download_url,
                    "invoice_id": invoice_obj.id,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON format in request body!"},
                status=400
            )
        except Item.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Item does not exist!"},
                status=400
            )
        except ValueError as ve:
            return JsonResponse(
                {"status": "error", "message": str(ve)},
                status=400
            )
        except TypeError as te:
            return JsonResponse(
                {"status": "error", "message": str(te)},
                status=400
            )
        except Exception as e:
            logger.error(f"Exception during sale creation: {e}")
            return JsonResponse(
                {"status": "error", "message": f"There was an error during the creation: {str(e)}"},
                status=500
            )

    return render(request, "transactions/sale_create.html", context=context)


class SaleDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Sale
    template_name = 'transactions/saledelete.html'
    success_url = reverse_lazy('saleslist')

    @property
    def archive_success_message(self):
        return 'Sale archived successfully.'


class PurchaseListView(CompanyAccessMixin, ListView):
    model = Purchase
    template_name = "transactions/purchases_list.html"
    context_object_name = "purchases"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("vendor")
            .order_by("-delivery_date", "-order_date", "-id")
        )

        search = self.request.GET.get("search", "").strip()
        from_date = self.request.GET.get("from_date", "").strip()
        to_date = self.request.GET.get("to_date", "").strip()

        if search:
            queryset = queryset.filter(
                Q(invoice_id__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(description__icontains=search)
            )

        if from_date:
            queryset = queryset.filter(delivery_date__gte=from_date)

        if to_date:
            queryset = queryset.filter(delivery_date__lte=to_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["search"] = self.request.GET.get("search", "")
        context["from_date"] = self.request.GET.get("from_date", "")
        context["to_date"] = self.request.GET.get("to_date", "")

        return context


class PurchaseDetailView(CompanyAccessMixin, DetailView):
    model = Purchase
    template_name = "transactions/purchasedetail.html"
    context_object_name = "purchase"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.sync_payment_state(save=True)
        context["purchase_items"] = self.object.purchase_items.select_related("item").all()
        context["payment_records"] = self.object.payments.filter(
            is_archived=False,
        ).order_by('-paid_on', '-id')
        return context


@login_required
def PurchaseCreateView(request):
    company = resolve_request_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('owner-login')

    context = {
        'active_icon': 'purchases',
        'items': scoped_queryset(Item, request.user).order_by('name'),
        'vendors': scoped_queryset(Vendor, request.user).order_by('name'),
        'categories': scoped_queryset(Category, request.user).order_by('name'),
        "payment_mode_choices": Purchase._meta.get_field("payment_mode").choices,
    }

    if request.method == "POST" and is_ajax(request=request):
        try:
            data = json.loads(request.body)
            logger.info(f"Received purchase data: {data}")

            vendor_name = normalize_text(data.get("vendor_name", ""))
            vendor_phone_number_raw = normalize_text(data.get("vendor_phone_number", ""))
            vendor_email = normalize_text(data.get("vendor_email", ""))
            vendor_gst_number = normalize_text(data.get("vendor_gst_number", ""))
            vendor_address = normalize_text(data.get("vendor_address", ""))
            invoice_id = normalize_text(data.get("invoice_id", ""))

            purchase_note = str(data.get("description", "")).strip()
            payment_mode = data.get("payment_mode", "CASH")
            delivery_date_raw = data.get("delivery_date", "")
            amount_paid_raw = data.get("amount_paid", 0)
            rows = data.get("rows", [])

            valid_payment_modes = [
                "NONE", "CASH", "CREDIT_CARD", "DEBIT_CARD",
                "CHEQUE", "UPI", "BANK_TRANSFER", "OTHER"
            ]

            if not vendor_name:
                raise ValueError("Vendor is required")

            if not invoice_id:
                raise ValueError("Invoice ID is required")

            existing_purchase = scoped_queryset(Purchase, request.user).filter(
                invoice_id__iexact=invoice_id
            ).first()
            if existing_purchase:
                raise ValueError("Invoice ID already exists")

            if payment_mode not in valid_payment_modes:
                raise ValueError("Invalid payment mode")

            if not isinstance(rows, list) or len(rows) == 0:
                raise ValueError("Add at least one product row")

            try:
                initial_amount_paid = Decimal(str(amount_paid_raw or 0))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("Invalid amount paid")

            if initial_amount_paid < 0:
                raise ValueError("Amount paid cannot be negative")

            delivery_date = None
            purchase_datetime = None

            if delivery_date_raw:
                delivery_date = parse_date(delivery_date_raw)
                if delivery_date is None:
                    raise ValueError("Invalid purchase date")
                purchase_datetime = timezone.make_aware(
                    datetime.combine(delivery_date, time.min),
                )

            vendor_obj = scoped_queryset(Vendor, request.user).filter(
                name__iexact=vendor_name,
            ).first()

            vendor_phone_number = None
            if vendor_phone_number_raw:
                try:
                    vendor_phone_number = int(vendor_phone_number_raw)
                except ValueError:
                    raise ValueError("Vendor phone number must contain digits only")

            if vendor_obj is None:
                vendor_obj = Vendor.objects.create(
                    name=vendor_name,
                    phone_number=vendor_phone_number,
                    email=vendor_email or None,
                    gst_number=vendor_gst_number or None,
                    address=vendor_address or None,
                    company=company,
                    created_by=request.user,
                    updated_by=request.user,
                )
            else:
                vendor_obj.phone_number = vendor_phone_number
                vendor_obj.email = vendor_email or None
                vendor_obj.gst_number = vendor_gst_number or None
                vendor_obj.address = vendor_address or None
                vendor_obj.save()

            prepared_rows = []
            batch_total = Decimal("0.00")

            for row in rows:
                item_name = normalize_text(row.get("item_name", ""))
                category_name = normalize_text(row.get("category_name", ""))
                item_description = normalize_text(row.get("item_description", ""))
                quantity_raw = row.get("quantity", 0)
                price_raw = row.get("price", 0)
                gst_raw = row.get("gst_percentage", 0)
                hsn_code = normalize_text(row.get("hsn_code", ""))

                if not item_name:
                    raise ValueError("Product name is required in every row")

                try:
                    quantity = int(quantity_raw)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid quantity for product: {item_name}")

                try:
                    price = Decimal(str(price_raw))
                except (InvalidOperation, TypeError, ValueError):
                    raise ValueError(f"Invalid price for product: {item_name}")

                try:
                    gst_percentage = Decimal(str(gst_raw or 0))
                except (InvalidOperation, TypeError, ValueError):
                    raise ValueError(f"Invalid GST for product: {item_name}")

                if quantity <= 0:
                    raise ValueError(f"Quantity must be greater than 0 for product: {item_name}")

                if price < 0:
                    raise ValueError(f"Price cannot be negative for product: {item_name}")

                if gst_percentage < 0:
                    raise ValueError(f"GST cannot be negative for product: {item_name}")

                category_obj = None
                if category_name:
                    category_obj = Category.objects.filter(
                        company=company,
                        name__iexact=category_name,
                        is_archived=False,
                    ).first()

                    if category_obj is None:
                        category_obj = Category.objects.create(
                            name=category_name,
                            company=company,
                            created_by=request.user,
                            updated_by=request.user,
                        )

                item_obj = Item.objects.filter(
                    company=company,
                    name__iexact=item_name,
                    is_archived=False,
                ).first()

                if item_obj is None:
                    if not category_name:
                        raise ValueError(f"Category is required for new product: {item_name}")

                    if not item_description:
                        raise ValueError(f"Description is required for new product: {item_name}")

                base_total = Decimal(quantity) * price
                gst_amount = base_total * (gst_percentage / Decimal("100"))
                line_total = base_total + gst_amount
                batch_total += line_total

                prepared_rows.append({
                    "item_obj": item_obj,
                    "item_name": item_name,
                    "item_description": item_description,
                    "category_obj": category_obj,
                    "quantity": quantity,
                    "price": price,
                    "gst_percentage": gst_percentage,
                    "hsn_code": hsn_code,
                })

            if initial_amount_paid > batch_total:
                raise ValueError("Amount paid cannot exceed total amount")

            with transaction.atomic():
                purchase_obj = Purchase.objects.create(
                    vendor=vendor_obj,
                    company=company,
                    invoice_id=invoice_id,
                    description=purchase_note,
                    delivery_date=delivery_date,
                    payment_mode=payment_mode,
                    amount_paid=Decimal('0.00'),
                    delivery_status='P',
                    created_by=request.user,
                    updated_by=request.user,
                )

                for row in prepared_rows:
                    item_obj = row["item_obj"]

                    if item_obj is None:
                        item_obj = Item.objects.create(
                            name=row["item_name"],
                            description=row["item_description"],
                            category=row["category_obj"],
                            company=company,
                            quantity=row["quantity"],
                            price=float(row["price"]),
                            gst_percentage=float(row["gst_percentage"]),
                            hsn_code=row["hsn_code"],
                            purchase_date=purchase_datetime,
                            vendor=vendor_obj,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    else:
                        if row["category_obj"] is not None:
                            item_obj.category = row["category_obj"]

                        if row["item_description"]:
                            item_obj.description = row["item_description"]

                        item_obj.price = float(row["price"])
                        item_obj.gst_percentage = float(row["gst_percentage"])

                        if row["hsn_code"]:
                            item_obj.hsn_code = row["hsn_code"]

                        item_obj.vendor = vendor_obj
                        item_obj.purchase_date = purchase_datetime
                        item_obj.quantity += row["quantity"]

                        item_obj.save()

                    PurchaseItem.objects.create(
                        purchase=purchase_obj,
                        item=item_obj,
                        company=company,
                        quantity=row["quantity"],
                        price=row["price"],
                        gst_percentage=row["gst_percentage"],
                    )

                if initial_amount_paid > 0:
                    PurchasePayment.objects.create(
                        purchase=purchase_obj,
                        company=company,
                        amount=initial_amount_paid,
                        payment_mode=payment_mode,
                        note='Initial payment',
                    )

                purchase_obj.sync_payment_state(save=True)

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Purchase created successfully!",
                    "redirect": reverse("purchaseslist")
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON format in request body!"},
                status=400
            )
        except ValueError as ve:
            return JsonResponse(
                {"status": "error", "message": str(ve)},
                status=400
            )
        except Exception as e:
            logger.error(f"Exception during purchase creation: {e}")
            return JsonResponse(
                {"status": "error", "message": f"There was an error during the creation: {str(e)}"},
                status=500
            )

    return render(request, "transactions/purchase_create.html", context=context)


def add_purchase_payment(request, pk):
    purchase = get_object_or_404(
        filter_by_company(Purchase.objects.all(), request.user),
        pk=pk,
    )

    if request.method == "POST":
        purchase.sync_payment_state(save=True)

        amount_raw = request.POST.get("amount", "0")
        payment_mode = request.POST.get("payment_mode", "CASH")
        note = request.POST.get("note", "").strip()

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Invalid payment amount.")
            return redirect("purchase-detail", slug=purchase.slug)

        if amount <= 0:
            messages.error(request, "Payment amount must be greater than 0.")
            return redirect("purchase-detail", slug=purchase.slug)

        if amount > purchase.remaining_amount:
            messages.error(request, "Payment amount cannot exceed remaining amount.")
            return redirect("purchase-detail", slug=purchase.slug)

        PurchasePayment.objects.create(
            purchase=purchase,
            company=purchase.company,
            amount=amount,
            payment_mode=payment_mode,
            note=note,
        )

        purchase.payment_mode = payment_mode
        purchase.save(update_fields=["payment_mode"])
        purchase.sync_payment_state(save=True)

        messages.success(request, "Payment recorded successfully.")

    return redirect("purchase-detail", slug=purchase.slug)


class PurchaseUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_success_url(self):
        return reverse("purchaseslist")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.sync_payment_state(save=True)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.sync_payment_state(save=True)
        context['vendors'] = filter_by_company(
            Vendor.objects.all(), self.request.user,
        ).order_by('name')
        context["purchase_items"] = self.object.purchase_items.select_related("item").all()
        context["payment_records"] = self.object.payments.all()
        return context


@login_required
def add_sale_payment(request, pk):
    sale = get_object_or_404(
        filter_by_company(Sale.objects.all(), request.user),
        pk=pk,
    )

    if request.method == 'POST':
        sale.sync_payment_state(save=True)

        amount_raw = request.POST.get('amount', '0')
        payment_mode = request.POST.get('payment_mode', 'CASH')
        note = request.POST.get('note', '').strip()

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, 'Invalid payment amount.')
            return redirect('sale-detail', pk=sale.pk)

        if amount <= 0:
            messages.error(request, 'Payment amount must be greater than 0.')
            return redirect('sale-detail', pk=sale.pk)

        if amount > sale.remaining_amount:
            messages.error(
                request,
                'Payment amount cannot exceed remaining amount.',
            )
            return redirect('sale-detail', pk=sale.pk)

        SalePayment.objects.create(
            sale=sale,
            company=sale.company,
            amount=amount,
            payment_mode=payment_mode,
            note=note,
            created_by=request.user,
            updated_by=request.user,
        )
        sale.sync_payment_state(save=True)
        messages.success(request, 'Payment recorded successfully.')

    return redirect('sale-detail', pk=sale.pk)


@login_required
def update_sale_payment(request, pk):
    payment = get_object_or_404(
        filter_by_company(
            SalePayment.objects.filter(is_archived=False),
            request.user,
        ),
        pk=pk,
    )

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0')
        payment_mode = request.POST.get('payment_mode', 'CASH')
        note = request.POST.get('note', '').strip()

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, 'Invalid payment amount.')
            return redirect('sale-detail', pk=payment.sale_id)

        if amount <= 0:
            messages.error(request, 'Payment amount must be greater than 0.')
            return redirect('sale-detail', pk=payment.sale_id)

        other_paid = payment.sale.payments.filter(
            is_archived=False,
        ).exclude(pk=payment.pk).aggregate(
            total=Sum('amount'),
        ).get('total') or Decimal('0.00')

        if amount + other_paid > payment.sale.grand_total:
            messages.error(
                request,
                'Total payments cannot exceed the sale grand total.',
            )
            return redirect('sale-detail', pk=payment.sale_id)

        payment.amount = amount
        payment.payment_mode = payment_mode
        payment.note = note
        payment.updated_by = request.user
        payment.save()
        payment.sale.sync_payment_state(save=True)
        messages.success(request, 'Payment updated successfully.')

    return redirect('sale-detail', pk=payment.sale_id)


class SalePaymentUpdateView(CoordinatorOrAdminMixin, UpdateView):
    model = SalePayment
    fields = ['amount', 'payment_mode', 'note']
    template_name = 'transactions/sale_payment_form.html'

    def get_queryset(self):
        return filter_by_company(
            SalePayment.objects.filter(is_archived=False),
            self.request.user,
        )

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.updated_by = self.request.user
        self.object.save()
        self.object.sale.sync_payment_state(save=True)
        messages.success(self.request, 'Payment updated successfully.')
        return redirect('sale-detail', pk=self.object.sale_id)


class SalePaymentArchiveView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        payment = get_object_or_404(
            filter_by_company(
                SalePayment.objects.filter(is_archived=False),
                request.user,
            ),
            pk=pk,
        )
        archive_instance(payment, request.user)
        payment.sale.sync_payment_state(save=True)
        messages.success(request, 'Payment archived successfully.')
        return redirect('sale-detail', pk=payment.sale_id)


class PurchaseDeleteView(CompanyAdminRequiredMixin, ArchivableDeleteView):
    model = Purchase
    template_name = 'transactions/purchasedelete.html'
    success_url = reverse_lazy('purchaseslist')

    @property
    def archive_success_message(self):
        return 'Purchase archived successfully.'


@login_required
def archive_purchase_payment(request, pk):
    if request.method != 'POST':
        return redirect('purchaseslist')

    profile = getattr(request.user, 'profile', None)
    if not request.user.is_superuser and (
        profile is None or not profile.is_company_admin()
    ):
        messages.error(request, 'Only company admins can archive payments.')
        return redirect('purchaseslist')

    payment = get_object_or_404(
        filter_by_company(
            PurchasePayment.objects.filter(is_archived=False),
            request.user,
        ),
        pk=pk,
    )
    archive_instance(payment, request.user)
    payment.purchase.sync_payment_state(save=True)
    messages.success(request, 'Purchase payment archived successfully.')
    return redirect('purchase-detail', slug=payment.purchase.slug)