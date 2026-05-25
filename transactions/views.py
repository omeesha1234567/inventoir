import json
import logging

from decimal import Decimal, InvalidOperation
from datetime import datetime, time

from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin, UpdateView, DeleteView
from openpyxl import Workbook

from invoice.models import Invoice, InvoiceItem
from store.models import Item, Category
from accounts.models import Customer, Vendor
from .models import Sale, Purchase, SaleDetail, PurchaseItem, PurchasePayment
from .forms import PurchaseForm

logger = logging.getLogger(__name__)


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def normalize_text(value):
    return " ".join(str(value or "").split()).strip()



def split_customer_name(customer_name):
    customer_name = normalize_text(customer_name)
    if not customer_name:
        return "", ""

    name_parts = customer_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    return first_name, last_name


def get_customer_details(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405
        )

    try:
        customer_name = request.POST.get("customer_name", "").strip()
        first_name, last_name = split_customer_name(customer_name)

        if not first_name:
            return JsonResponse(
                {"status": "success", "found": False, "phone": "", "address": ""}
            )

        customer = Customer.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name
        ).first()

        if customer is None:
            return JsonResponse(
                {"status": "success", "found": False, "phone": "", "address": ""}
            )

        return JsonResponse(
            {
                "status": "success",
                "found": True,
                "phone": customer.phone or "",
                "address": customer.address or ""
            }
        )

    except Exception as e:
        logger.error(f"Error fetching customer details: {e}")
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500
        )


def get_vendor_details(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405
        )

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

        vendor = Vendor.objects.filter(name__iexact=vendor_name).first()

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

    sales = Sale.objects.all()

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

    purchases = Purchase.objects.all()

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


class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = "transactions/sales_list.html"
    context_object_name = "sales"
    paginate_by = 10

    def get_queryset(self):
        return Sale.objects.select_related("customer").order_by("-date_added", "-id")


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = "transactions/saledetail.html"
    context_object_name = "sale"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sale_items"] = self.object.saledetail_set.select_related("item").all()
        return context


def SaleCreateView(request):
    context = {
        "active_icon": "sales",
        "customers": Customer.objects.all().order_by("first_name", "last_name"),
        "items": Item.objects.all().order_by("name"),
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

            if not customer_name:
                raise ValueError("Customer name is required")

            first_name, last_name = split_customer_name(customer_name)

            customer_instance = Customer.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name
            ).first()

            if customer_instance is None:
                customer_instance = Customer.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    address=address
                )
            else:
                customer_instance.phone = phone
                customer_instance.address = address
                customer_instance.save()

            items = data.get("items")
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError("At least one item is required")

            amount_paid = float(data.get("amount_paid", 0))
            grand_total = 0

            with transaction.atomic():
                new_sale = Sale.objects.create(
                    customer=customer_instance,
                    sub_total=0,
                    grand_total=0,
                    tax_amount=0,
                    tax_percentage=0,
                    amount_paid=amount_paid,
                    amount_change=0,
                )

                for item in items:
                    if "id" not in item or "quantity" not in item:
                        raise ValueError("Item is missing required fields")

                    item_instance = Item.objects.select_for_update().get(
                        id=int(item["id"])
                    )

                    quantity = int(item.get("quantity", 0))
                    margin = float(item.get("margin", 0))
                    gst_percentage = float(
                        item.get("gst_percentage", item_instance.gst_percentage)
                    )

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

                    original_price = float(item_instance.price)
                    total_item = (
                        (original_price + margin)
                        + ((original_price + margin) * gst_percentage / 100)
                    ) * quantity

                    total_item = round(total_item, 2)
                    grand_total += total_item

                    SaleDetail.objects.create(
                        sale=new_sale,
                        item=item_instance,
                        price=round(original_price, 2),
                        quantity=quantity,
                        total_detail=total_item
                    )

                    item_instance.quantity -= quantity
                    item_instance.save()

                new_sale.sub_total = round(grand_total, 2)
                new_sale.grand_total = round(grand_total, 2)
                new_sale.amount_change = round(amount_paid - grand_total, 2)
                new_sale.save()

                invoice_obj, created = Invoice.objects.get_or_create(
                    sale=new_sale,
                    defaults={"shipping": 0}
                )

                if not created:
                    invoice_obj.invoice_items.all().delete()

                for detail in new_sale.saledetail_set.all():
                    InvoiceItem.objects.create(
                        invoice=invoice_obj,
                        item=detail.item,
                        price=float(detail.price),
                        quantity=float(detail.quantity),
                        line_total=float(detail.total_detail)
                    )

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Sale created successfully!",
                    "redirect": reverse("saleslist")
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


class SaleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Sale
    template_name = "transactions/saledelete.html"

    def get_success_url(self):
        return reverse("saleslist")

    def test_func(self):
        return self.request.user.is_superuser


class PurchaseListView(LoginRequiredMixin, ListView):
    model = Purchase
    template_name = "transactions/purchases_list.html"
    context_object_name = "purchases"
    paginate_by = 10
    ordering = ['-delivery_date', '-order_date', '-id']


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    model = Purchase
    template_name = "transactions/purchasedetail.html"
    context_object_name = "purchase"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.sync_payment_state(save=True)
        context["purchase_items"] = self.object.purchase_items.select_related("item").all()
        context["payment_records"] = self.object.payments.all()
        return context


def PurchaseCreateView(request):
    context = {
        "active_icon": "purchases",
        "items": Item.objects.all().order_by("name"),
        "vendors": Vendor.objects.all().order_by("name"),
        "categories": Category.objects.all().order_by("name"),
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
                purchase_datetime = datetime.combine(delivery_date, time.min)

            vendor_obj = Vendor.objects.filter(name__iexact=vendor_name).first()

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
                    address=vendor_address or None
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
                    category_obj = Category.objects.filter(name__iexact=category_name).first()
                    if category_obj is None:
                        category_obj = Category.objects.create(name=category_name)

                item_obj = Item.objects.filter(name__iexact=item_name).first()

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
                })

            if initial_amount_paid > batch_total:
                raise ValueError("Amount paid cannot exceed total amount")

            with transaction.atomic():
                purchase_obj = Purchase.objects.create(
                    vendor=vendor_obj,
                    description=purchase_note,
                    delivery_date=delivery_date,
                    payment_mode=payment_mode,
                    amount_paid=Decimal("0.00"),
                    delivery_status="P",
                )

                for row in prepared_rows:
                    item_obj = row["item_obj"]

                    if item_obj is None:
                        item_obj = Item.objects.create(
                            name=row["item_name"],
                            description=row["item_description"],
                            category=row["category_obj"],
                            quantity=0,
                            price=float(row["price"]),
                            gst_percentage=float(row["gst_percentage"]),
                            purchase_date=purchase_datetime,
                            vendor=vendor_obj
                        )
                    else:
                        if row["category_obj"] is not None:
                            item_obj.category = row["category_obj"]
                        if row["item_description"]:
                            item_obj.description = row["item_description"]

                        item_obj.price = float(row["price"])
                        item_obj.gst_percentage = float(row["gst_percentage"])
                        item_obj.vendor = vendor_obj
                        item_obj.purchase_date = purchase_datetime
                        item_obj.save()

                    PurchaseItem.objects.create(
                        purchase=purchase_obj,
                        item=item_obj,
                        quantity=row["quantity"],
                        price=row["price"],
                        gst_percentage=row["gst_percentage"],
                    )

                    item_obj.quantity += row["quantity"]
                    item_obj.save(update_fields=["quantity"])

                if initial_amount_paid > 0:
                    PurchasePayment.objects.create(
                        purchase=purchase_obj,
                        amount=initial_amount_paid,
                        payment_mode=payment_mode,
                        note="Initial payment"
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
    purchase = get_object_or_404(Purchase, pk=pk)

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
            amount=amount,
            payment_mode=payment_mode,
            note=note
        )

        purchase.payment_mode = payment_mode
        purchase.save(update_fields=["payment_mode"])
        purchase.sync_payment_state(save=True)

        messages.success(request, "Payment recorded successfully.")

    return redirect("purchase-detail", slug=purchase.slug)


class PurchaseUpdateView(LoginRequiredMixin, UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"

    def get_success_url(self):
        return reverse("purchaseslist")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.sync_payment_state(save=True)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.sync_payment_state(save=True)
        context["vendors"] = Vendor.objects.all().order_by("name")
        context["purchase_items"] = self.object.purchase_items.select_related("item").all()
        context["payment_records"] = self.object.payments.all()
        return context


class PurchaseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Purchase
    template_name = "transactions/purchasedelete.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        for purchase_item in self.object.purchase_items.select_related("item").all():
            purchase_item.item.quantity -= purchase_item.quantity
            if purchase_item.item.quantity < 0:
                purchase_item.item.quantity = 0
            purchase_item.item.save(update_fields=["quantity"])

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("purchaseslist")

    def test_func(self):
        return self.request.user.is_superuser