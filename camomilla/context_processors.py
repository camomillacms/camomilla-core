from camomilla.models import Menu


def MenusContextProcessor(request):
    qs = Menu.objects.all()
    return {"menus": Menu.defaultdict(**{m.key: m for m in qs})}
