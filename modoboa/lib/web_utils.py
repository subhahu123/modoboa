# coding: utf-8

"""
This module contains extra functions/shortcuts used to render HTML.
"""

import json
import re
import sys

from django import template
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string


def _render_to_string(request, tpl, user_context):
    """Custom rendering function.

    Just a wrapper which automatically adds a RequestContext instance
    (useful to use settings variables like STATIC_URL inside templates)
    """
    return render_to_string(tpl, user_context,
                            context_instance=template.RequestContext(request))


def _render_error(request, errortpl="error", user_context=None):
    if user_context is None:
        user_context = {}
    return render(
        request, "common/%s.html" % errortpl, user_context
    )


def render_actions(actions):
    t = template.Template("""{% load lib_tags %}
{% for a in actions %}{% render_link a %}{% endfor %}
""")
    return t.render(template.Context(dict(actions=actions)))


def getctx(status, level=1, callback=None, **kwargs):
    if not callback:
        callername = sys._getframe(level).f_code.co_name
    else:
        callername = callback
    ctx = {"status": status, "callback": callername}
    for kw, v in kwargs.iteritems():
        ctx[kw] = v
    return ctx


def ajax_response(request, status="ok", respmsg=None,
                  url=None, ajaxnav=False, norefresh=False,
                  template=None, **kwargs):
    """Ajax response shortcut

    Simple shortcut that sends an JSON response. If a template is
    provided, a 'content' field will be added to the response,
    containing the result of this template rendering.

    :param request: a Request object
    :param status: the response status ('ok' or 'ko)
    :param respmsg: the message that will displayed in the interface
    :param url: url to display after receiving this response
    :param ajaxnav:
    :param norefresh: do not refresh the page after receiving this response
    :param template: eventual template's path
    :param kwargs: dict used for template rendering
    """
    ctx = {}
    for k, v in kwargs.iteritems():
        ctx[k] = v
    if template is not None:
        content = _render_to_string(request, template, ctx)
    elif "content" in kwargs:
        content = kwargs["content"]
    else:
        content = ""
    jsonctx = {"status": status, "content": content}
    if respmsg is not None:
        jsonctx["respmsg"] = respmsg
    if ajaxnav:
        jsonctx["ajaxnav"] = True
    if url is not None:
        jsonctx["url"] = url
    jsonctx["norefresh"] = norefresh
    return HttpResponse(json.dumps(jsonctx), mimetype="application/json")


def render_to_json_response(context, **response_kwargs):
    """Simple shortcut to render a JSON response.

    :param dict context: response content
    :return: ``HttpResponse`` object
    """
    data = json.dumps(context)
    response_kwargs['content_type'] = 'application/json'
    return HttpResponse(data, **response_kwargs)


def static_url(path):
    """Returns the correct static url for a given file

    :param path: the targeted static media
    """
    if path.startswith("/"):
        path = path[1:]
    return "%s%s" % (settings.STATIC_URL, path)


def size2integer(value):
    """Try to convert a string representing a size to an integer value
    in bytes.

    Supported formats:
    * K|k for KB
    * M|m for MB
    * G|g for GB

    :param value: the string to convert
    :return: the corresponding integer value
    """
    m = re.match("(\d+)\s*(\w+)", value)
    if m is None:
        if re.match("\d+", value):
            return int(value)
        return 0
    if m.group(2)[0] in ["K", "k"]:
        return int(m.group(1)) * 2 ** 10
    if m.group(2)[0] in ["M", "m"]:
        return int(m.group(1)) * 2 ** 20
    if m.group(2)[0] in ["G", "g"]:
        return int(m.group(1)) * 2 ** 30
    return 0


@login_required
def topredirection(request):
    """Simple view to redirect the request when no application is specified.

    The default "top redirection" can be specified in the *Admin >
    Settings* panel. It is the application that will be
    launched. Those not allowed to access the application will be
    redirected to their preferences page.

    This feature only applies to simple users.

    :param request: a Request object
    """
    from modoboa.lib import parameters
    from modoboa.core.extensions import exts_pool

    if request.user.group == 'SimpleUsers':
        topredir = parameters.get_admin("DEFAULT_TOP_REDIRECTION", app="core")
        if topredir != "user":
            infos = exts_pool.get_extension_infos(topredir)
            path = infos["url"] if infos["url"] else infos["name"]
        else:
            path = reverse("core:user_index")
    else:
        path = reverse("admin:domain_list")
    return HttpResponseRedirect(path)


class NavigationParameters(object):
    """
    Just a simple object to manipulate navigation parameters.
    """

    def __init__(self, request, sessionkey):
        self.request = request
        self.sessionkey = sessionkey
        self.parameters = [('pattern', '', True),
                           ('criteria', 'from_addr', False)]

    def __getitem__(self, key):
        """Retrieve an item."""
        if self.sessionkey not in self.request.session:
            raise KeyError
        return self.request.session[self.sessionkey][key]

    def __contains__(self, key):
        """Check if key is present."""
        if self.sessionkey not in self.request.session:
            return False
        return key in self.request.session[self.sessionkey]

    def __setitem__(self, key, value):
        """Set a new item."""
        self.request.session[self.sessionkey][key] = value

    def _store_page(self):
        """Specific method to store the current page."""
        self["page"] = int(self.request.GET.get("page", 1))

    def store(self):
        """Store navigation parameters into session.
        """
        if self.sessionkey not in self.request.session:
            self.request.session[self.sessionkey] = {}
        self._store_page()
        navparams = self.request.session[self.sessionkey]
        navparams["order"] = self.request.GET.get("sort_order", "-date")
        for param, defvalue, escape in self.parameters:
            value = self.request.GET.get(param, defvalue)
            if value is None:
                if param in navparams:
                    del navparams[param]
                continue
            navparams[param] = re.escape(value) if escape else value
        self.request.session.modified = True

    def get(self, param, default_value=None):
        """Retrieve a navigation parameter.

        Just a simple getter to avoid using the full key name to
        access a parameter.

        :param str param: parameter name
        :param defaultvalue: default value if none is found
        :return: parameter's value
        """
        if self.sessionkey not in self.request.session:
            return default_value
        return self.request.session[self.sessionkey].get(param, default_value)

    def remove(self, param):
        """Remove a navigation parameter from session.

        :param str param: parameter name
        """
        navparams = self.request.session[self.sessionkey]
        if param in navparams:
            del navparams[param]