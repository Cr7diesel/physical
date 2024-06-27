from datetime import date
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import View

from .models import (
    Orders,
    Comments,
    Ordercomresponsible,
    CustomersList,
    Customer,
    Orderresponsible,
    Costs,
    Approvedlists,
    Favorites,
)


class BaseMixin(LoginRequiredMixin, View):
    def get(self, request):
        try:
            objects = self.get_objects()
            search = request.user.search
            if search.search:
                objects = objects.filter(self.get_search_filter(request))

            if search.goal:
                objects = objects.filter(**{self.set_prefix() + "goal": True})

            if search.favorite:
                fav = Favorites.objects.filter(user=request.user)
                orders_fav = fav.values_list('order__orderid', flat=True)
                objects = objects.filter(orderid__in=orders_fav)

            objects = self.filter_by_manager(request, objects)

            if search.stage:
                objects = objects.filter(
                    **{self.set_prefix() + "stageid": search.stage}
                )
            if search.company:
                objects = objects.filter(
                    Q(**{self.set_prefix() + "cityid": None})
                    | Q(**{self.set_prefix() + "cityid": search.company})
                )
            if search.customer:
                objects = objects.filter(
                    **{
                        self.set_prefix()
                        + "searchowners__icontains": search.customer
                    }
                )

            if request.GET.get("action") == "count":
                return JsonResponse({"count": objects.count()})

            try:
                start = int(request.GET.get("start", 0))
                stop = int(request.GET.get("stop", 1))
            except ValueError:
                start = 0
                stop = 0

            context = self.get_context_data(request, objects[start:stop])

            return render(request, self.set_template_name(), context)

        except ObjectDoesNotExist:
            return JsonResponse({"error": "Object does not exist"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class OrderList(BaseMixin):

    def get_objects(self):
        return Orders.objects.all()

    def get_search_filter(self, request):
        search = request.user.search
        return Q(name__icontains=search.search) | Q(
            searchowners__icontains=search.search
        )

    def set_prefix(self):
        return ""

    def get_context_data(self, request, orders):
        orders = orders.order_by("-reiting")
        customers = []
        last_contact = []
        resp = []
        favorite = []
        task = []

        orders = orders.select_related(
            'customer').prefetch_related('comments', 'orderresponsible_set', 'ordercomresponsible_set')
        for order in orders:
            resp.append(Orderresponsible.objects.filter(orderid=order.orderid))
            customers_list = CustomersList.objects.filter(orderid=order.orderid).order_by(
                "customerid__title"
            )
            customers.append(customers_list)
            last_comment = Comments.objects.filter(orderid=order).first()
            last_contact.append(last_comment.createdat if last_comment else "")
            task_count = Comments.objects.filter(
                orderid=order).filter(istask=1).exclude(complete=1).count()
            task.append(task_count)
            is_favorite = Favorites.objects.filter(user=request.user, order=order).exists()
            favorite.append(is_favorite)

        context = {
            "orders": zip(orders, customers, favorite, last_contact, task, resp),
            "today": date.today(),
        }
        return context

    def filter_by_manager(self, request, objects):
        search = request.user.search
        if search.manager:
            order_res = Ordercomresponsible.objects.filter(
                user=search.manager).values_list("orderid__orderid", flat=True)
            res = Orderresponsible.objects.filter(
                user=search.manager).exclude(orderid__orderid__in=order_res).values_list("orderid__orderid", flat=True)
            objects = objects.filter(orderid__in=res)
        return objects

    def set_template_name(self):
        return "main/orders_list.html"


class CostList(BaseMixin):

    def get_objects(self):
        return Costs.objects.all()

    def get_search_filter(self, request):
        search = request.user.search
        return (
            Q(description__icontains=search.search)
            | Q(section__icontains=search.search)
            | Q(orderid__name__icontains=search.search)
        )

    def set_prefix(self):
        return "orderid__"

    def get_context_data(self, request, costs):
        costs = costs.order_by("-createdat")
        appr = [Approvedlists.objects.filter(cost_id=cost) for cost in costs]
        context = {"costs": zip(costs, appr), "today": date.today()}
        return context

    def filter_by_manager(self, request, objects):
        search = request.user.search
        if search.manager:
            objects = objects.filter(user=search.manager)
        return objects

    def set_template_name(self):
        return "main/cost_list.html"
