from django import forms
from .models import Hook, Dialout
from django.utils.translation import ugettext_lazy as _


class HookForm(forms.Form):

    enable = forms.BooleanField(label=_('Aktivera automatisk uppringning'), required=False)
    recording_key = forms.CharField(label=_('Inspelningsnyckel för automatisk inspelning'), required=False)

    def __init__(self, *args, **kwargs):
        from customer.models import Customer

        self.cospace = kwargs.pop('cospace', None)
        self.customer: Customer = kwargs.pop('customer', None)

        initial = kwargs.pop('initial', None) or {}

        kwargs['initial'] = initial

        if self.cospace is None:
            self.cospace = initial.get('cospace')

        if self.customer is None:
            self.customer = initial.get('customer')

        self.provider = self.customer.get_provider()

        hook = self.get_hook()
        if hook:
            initial['enable'] = hook.is_active
            initial['recording_key'] = hook.recording_key

        super().__init__(*args, **kwargs)

        try:
            is_videocenter = self.customer.get_videocenter_provider().is_videocenter
        except AttributeError:
            is_videocenter = False

        if not is_videocenter:
            self.fields.pop('recording_key', None)

    def get_hook(self):

        try:
            hook = Hook.objects.get(customer=self.customer, provider=self.provider,
                provider_ref=self.cospace)
            return hook
        except Hook.DoesNotExist:
            return None

    def save(self, commit=True):

        c = self.cleaned_data

        hook = self.get_hook()
        if not hook:
            if not c.get('enable'):
                return None
            hook = Hook(customer=self.customer, provider=self.provider,
                provider_ref=self.cospace)

        hook.is_active = c.get('enable')
        hook.recording_key = c.get('recording_key') or ''

        if commit:
            hook.save()
        return hook


class DialoutForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.hook = kwargs.pop('hook', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Dialout
        exclude = ('hook',)

    def save(self, *args, **kwargs):
        self.instance.hook = self.hook
        return super().save(*args, **kwargs)
