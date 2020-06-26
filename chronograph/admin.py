import django
from django.contrib import admin
from django.db import models
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponseRedirect, Http404
if django.VERSION < (1, 9):
    from django.conf.urls import patterns, url
else:
    from django.conf.urls import url
    def patterns(_, *urls):
        return list(urls)
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import escape, format_html, linebreaks
try:
    from django.contrib.admin.utils import display_for_field
except ImportError:
    from django.contrib.admin.util import display_for_field
    

from chronograph.models import Job, Log


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        widgets = {
            'command': forms.Textarea(attrs={'cols': 80, 'rows': 6}),
            'shell_command': forms.Textarea(attrs={'cols': 80, 'rows': 6}),
            'args': forms.Textarea(attrs={'cols': 80, 'rows': 6}),
        }
        exclude = []

    def clean_shell_command(self):
        if self.cleaned_data.get('command', '').strip() and \
                self.cleaned_data.get('shell_command', '').strip():
            raise forms.ValidationError(_("Can't specify a shell_command if "
                              "a django admin command is already specified"))
        return self.cleaned_data['shell_command']

    def clean(self):
        cleaned_data = super(JobForm, self).clean()
        if len(cleaned_data.get('command', '').strip()) and \
                len(cleaned_data.get('shell_command', '').strip()):
            raise forms.ValidationError(_("Must specify either command or "
                                        "shell command"))
        return cleaned_data


class JobAdmin(admin.ModelAdmin):
    actions = ['disable_jobs', 'reset_jobs']
    form = JobForm
    list_display = (
        'job_success', 'name', 'last_run_with_link', 'next_run', 'get_timeuntil',
        'frequency', 'is_running', 'run_button', 'view_logs_button',
    )
    list_display_links = ('name', )
    list_filter = ('last_run_successful', 'frequency', 'disabled')
    search_fields = ('name', )
    ordering = ('last_run', )
    filter_horizontal = ('subscribers', 'info_subscribers')

    fieldsets = (
        (_('Job Details'), {
            'classes': ('wide',),
            'fields': ('name', 'command', 'shell_command', 'run_in_shell', 'args', 'disabled',)
        }),
        (_('E-mail subscriptions'), {
            'classes': ('wide',),
            'fields': ('info_subscribers', 'subscribers',)
        }),
        (_('Frequency options'), {
            'classes': ('wide',),
            'fields': ('frequency', 'next_run', 'params',)
        }),
    )

    def disable_jobs(self, request, queryset):
        return queryset.update(disabled=True)

    def reset_jobs(self, request, queryset):
        return queryset.update(is_running=False)

    def last_run_with_link(self, obj):
        value = display_for_field(obj.last_run,
                                  obj._meta.get_field('last_run'),
                                  '')
        log_id = obj.log_set.latest('run_date').id
        try:
            # Old way
            reversed_url = reverse('chronograph_log_change', args=(log_id,))
        except:
            # New way
            reversed_url = reverse('admin:chronograph_log_change', args=(log_id,))

        return '<a href="%s">%s</a>' % (reversed_url, value)
    last_run_with_link.allow_tags = True
    last_run_with_link.short_description = _('Last run')
    last_run_with_link.admin_order_field = 'last_run'

    def job_success(self, obj):
        return obj.last_run_successful
    job_success.short_description = _(u'OK')
    job_success.boolean = True

    def run_button(self, obj):
        on_click = "window.location='%d/run/?inline=1';" % obj.id
        return '<input type="button" onclick="%s" value="Run" />' % on_click
    run_button.allow_tags = True
    run_button.short_description = _('Run')

    def view_logs_button(self, obj):
        on_click = "window.location='../log/?job=%d';" % obj.id
        return '<input type="button" onclick="%s" value="View Logs" />' % on_click
    view_logs_button.allow_tags = True
    view_logs_button.short_description = _('Logs')

    def run_job_view(self, request, pk):
        """
        Runs the specified job.
        """
        try:
            job = Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            raise Http404
        job.run()
        message = _('The job "%(job)s" was run successfully.') % {'job': job}
        if hasattr(self, 'message_user'):
            self.message_user(request, message)
        else:
            request.user.message_set.create(message=message)

        if 'inline' in request.GET:
            redirect = request.path + '../../'
        else:
            redirect = request.GET.get('next', request.path + "../")

        return HttpResponseRedirect(redirect)

    def get_urls(self):
        urls = super(JobAdmin, self).get_urls()
        my_urls = patterns('',
            url(r'^(.+)/run/$', self.admin_site.admin_view(self.run_job_view), name="chronograph_job_run"),
        )
        return my_urls + urls


class LogAdmin(admin.ModelAdmin):
    list_display = ('job_name', 'run_date', 'end_date', 'job_duration', 'job_success', 'output', 'errors', )
    search_fields = ('stdout', 'stderr', 'job__name', 'job__command')
    date_hierarchy = 'run_date'
    fieldsets = (
        (None, {
            'fields': ('job_display', 'run_date', 'end_date', 'job_duration', 'job_success',)
        }),
        (_('Output'), {
            'fields': ('stdout_display', 'stderr_display',)
        }),
    )
    readonly_fields = ('job_display', 'job_duration', 'job_success', 'run_date', 'end_date', 'stdout_display', 'stderr_display')

    def job_display(self, obj):
        related_url = reverse('admin:chronograph_job_change', args=(obj.pk,))
        return format_html('<a href="{0}">{1}</a>', related_url, obj)
    job_display.short_description = _('Job')

    def job_duration(self, obj):
        return "%s" % (obj.get_duration())
    job_duration.short_description = _(u'Duration')

    def job_name(self, obj):
        return obj.job.name
    job_name.short_description = _(u'Name')

    def job_success(self, obj):
        return obj.success
    job_success.short_description = _(u'OK')
    job_success.boolean = True

    def stdout_display(self, obj):
        return mark_safe('<div>{}</div>'.format(linebreaks(obj.stdout, autoescape=True)))
    stdout_display.short_description = _('Stdout')

    def stderr_display(self, obj):
        return mark_safe('<div>{}</div>'.format(linebreaks(obj.stderr, autoescape=True)))
    stderr_display.short_description = _('Stderr')

    def output(self, obj):
        result = obj.stdout or ''
        if len(result) > 40:
            result = result[:40] + '...'
        result = escape(result)

        return result or _('(No output)')

    def errors(self, obj):
        result = obj.stderr or ''
        if len(result) > 40:
            result = result[:40] + '...'
        result = escape(result)

        return result or _('(No errors)')

    def has_add_permission(self, request):
        return False


admin.site.register(Job, JobAdmin)
admin.site.register(Log, LogAdmin)
