from .models import Community

def communities_processor(request):
    communities = Community.objects.all().order_by('name')
    return {'global_communities': communities}
