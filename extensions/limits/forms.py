# coding: utf-8

from django import forms
from django.utils.translation import ugettext_noop as _
from django.contrib.auth.models import User, Group
from modoboa.admin.forms import UserForm, UserWithPasswordForm
from modoboa.admin.lib import get_object_owner
from models import *
from lib import *

class ResellerForm(UserForm):
    def __init__(self, *args, **kwargs):
        super(ResellerForm, self).__init__(*args, **kwargs)
        del self.fields["createmb"]

    def save(self, commit=True, group=None):
        user = super(ResellerForm, self).save(commit, group)
        if commit:
            try:
                pool = user.limitspool
            except LimitsPool.DoesNotExist:
                pool = LimitsPool()
                pool.user = user
                pool.save()
                pool.create_limits()

        return user

class ResellerWithPasswordForm(ResellerForm, UserWithPasswordForm):
    pass

class ResellerPoolForm(forms.Form):
    domains_limit = forms.IntegerField(ugettext_noop("Max domains"),
        help_text=ugettext_noop("Maximum number of domains that can be created by this user"))
    domain_aliases_limit = forms.IntegerField(ugettext_noop("Max domain aliases"),
        help_text=ugettext_noop("Maximum number of domain aliases that can be created by this user"))
    mailboxes_limit = forms.IntegerField(ugettext_noop("Max mailboxes"),
        help_text=ugettext_noop("Maximum number of mailboxes that can be created by this user"))
    mailbox_aliases_limit = forms.IntegerField(ugettext_noop("Max mailbox aliases"),
        help_text=ugettext_noop("Maximum number of mailbox aliases that can be created by this user"))

    def check_limit_value(self, lname):
        if self.cleaned_data[lname] < -1:
            raise forms.ValidationError(_("Invalid limit"))
        return self.cleaned_data[lname]

    def clean_domains_limit(self):
        return self.check_limit_value("domains_limit")

    def clean_domain_aliases_limit(self):
        return self.check_limit_value("domain_aliases_limit")

    def clean_mailboxes_limit(self):
        return self.check_limit_value("mailboxes_limit")

    def clean_mailbox_aliases_limit(self):
        return self.check_limit_value("mailbox_aliases_limit")

    def load_from_user(self, user):
        for l in reseller_limits_tpl:
            self.fields[l].initial = user.limitspool.getmaxvalue(l)

    def allocate_from_pool(self, limit, pool):
        ol = pool.get_limit(limit.name)
        if ol.maxvalue == -2:
            raise BadLimitValue(_("Your pool is not initialized yet"))
        newvalue = self.cleaned_data[limit.name]
        if newvalue == -1 and ol.maxvalue != -1:
            raise BadLimitValue(_("You're not allowed to define unlimited values"))

        if limit.maxvalue > -1:
            newvalue -= limit.maxvalue
            if newvalue == 0:
                return
        remain = ol.maxvalue - ol.curvalue
        if newvalue > remain:
            raise UnsifficientResource(ol)
        ol.maxvalue -= newvalue
        ol.save()

    def save_new_limits(self, pool):
        owner = get_object_owner(pool.user)
        for lname in reseller_limits_tpl:
            l = pool.limit_set.get(name=lname)
            if not owner.is_superuser:
                self.allocate_from_pool(l, owner.limitspool)
            l.maxvalue = self.cleaned_data[lname]
            l.save()

    