from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('papers/', views.paper_search_page, name='paper_search_page'),
    path('papers/results/', views.paper_search_results, name='paper_search_results'),
    path('papers/<str:paper_id>/', views.paper_detail_page, name='paper_detail_page')
]