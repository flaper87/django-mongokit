import datetime
from django.conf import settings
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404

from django_mongokit import get_database, connection


from models import Talk
from forms import TalkForm

def homepage(request):

    talks = Talk.objects.filter().order_by("-when")

    if request.method == "POST":
        form = TalkForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('homepage'))
    else:
        form = TalkForm()

    return render_to_response("exampleapp/home.html", locals(), 
                              context_instance=RequestContext(request))


def delete_talk(request, _id):
    Talk.objects.get(id=_id).delete()
    return HttpResponseRedirect(reverse("homepage"))
