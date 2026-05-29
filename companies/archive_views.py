"""Shared archive confirmation and POST handling for DeleteView subclasses."""
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic.edit import DeleteView

from companies.base import archive_instance


class ArchivableDeleteView(DeleteView):
    """
    GET shows archive confirmation template; POST archives (never hard-deletes).
    """

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_archived:
            archive_instance(self.object, request.user)
        messages.success(request, self.archive_success_message)
        return redirect(self.get_success_url())

    @property
    def archive_success_message(self):
        return f'{self.model._meta.verbose_name} archived successfully.'
