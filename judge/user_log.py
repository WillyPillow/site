from judge.models import Profile
from django.utils.timezone import now


class LogUserAccessMiddleware(object):
    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (hasattr(request, 'user') and request.user.is_authenticated and
                not getattr(request, 'no_profile_update', False)):
            updates = {'last_access': now()}
            def get_client_ip(request):
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                elif request.META.get('REMOTE_ADDR'):
                    ip = request.META.get('REMOTE_ADDR')
                else:
                    ip = None
                return ip

            ip = get_client_ip(request)
            if ip:
                updates['ip'] = ip
            Profile.objects.filter(user_id=request.user.pk).update(**updates)

        return response
