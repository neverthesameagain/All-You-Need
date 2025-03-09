from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Authentication URLs
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='content/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Article URLs
    path('create-article/', views.create_article, name='create_article'),
    path('edit-article/<int:pk>/', views.edit_article, name='edit_article'),
    path('delete-article/<int:pk>/', views.delete_article, name='delete_article'),
    path('article/<int:pk>/', views.article_detail, name='article_detail'),
    path('article/<int:pk>/vote/<str:vote_type>/', views.vote_article, name='vote_article'),
    path('article/<int:pk>/save/', views.save_article, name='save_article'),
    path('comment/<int:pk>/vote/<str:vote_type>/', views.vote_comment, name='vote_comment'),
    
    # User profile URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:username>/', views.profile_detail, name='profile_detail'),
    
    # Community URLs
    path('communities/', views.community_list, name='community_list'),
    path('communities/<int:pk>/', views.community_detail, name='community_detail'),
    path('communities/create/', views.create_community, name='create_community'),
    path('communities/<int:community_id>/join/', views.join_community, name='join_community'),
    path('communities/<int:community_id>/leave/', views.leave_community, name='leave_community'),
    path('communities/<int:community_id>/post/', views.create_article, name='community_create_article'),
    
    # Tag URLs
    path('tags/', views.tag_list, name='tag_list'),
    path('tags/create/', views.create_tag, name='create_tag'),
    path('tags/<slug:slug>/', views.tag_detail, name='tag_detail'),
    path('tags/<slug:slug>/edit/', views.edit_tag, name='edit_tag'),
    
    # Event URLs
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.create_event, name='create_event'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:pk>/edit/', views.edit_event, name='edit_event'),
    path('events/<int:pk>/join/', views.join_event, name='join_event'),
    path('events/<int:pk>/leave/', views.leave_event, name='leave_event'),
    path('events/<int:pk>/cancel/', views.cancel_event, name='cancel_event'),
    path('events/<int:pk>/feedback/', views.submit_feedback, name='submit_feedback'),
    
    # Resource Library URLs
    path('resources/', views.resource_list, name='resource_list'),
    path('resources/create/', views.create_resource, name='create_resource'),
    path('resources/<int:pk>/', views.resource_detail, name='resource_detail'),
    path('resources/<int:pk>/edit/', views.edit_resource, name='edit_resource'),
    path('resources/<int:pk>/delete/', views.delete_resource, name='delete_resource'),
    path('resources/<int:pk>/save/', views.save_resource, name='save_resource'),
    path('resources/<int:pk>/vote/<str:vote_type>/', views.vote_resource, name='vote_resource'),
    path('resources/categories/create/', views.create_category, name='create_category'),
    path('resources/categories/<slug:slug>/edit/', views.edit_category, name='edit_category'),
    
    # Study Room URLs
    path('study/', views.study_room_list, name='study_room_list'),
    path('study/create/', views.create_study_room, name='create_study_room'),
    path('study/<int:pk>/', views.study_room_detail, name='study_room_detail'),
    path('study/<int:pk>/join/', views.join_study_room, name='join_study_room'),
    path('study/<int:pk>/leave/', views.leave_study_room, name='leave_study_room'),
    path('study/<int:pk>/start-session/', views.start_study_session, name='start_study_session'),
    path('study/<int:pk>/end-session/<int:session_pk>/', views.end_study_session, name='end_study_session'),
    path('study/<int:pk>/chat/', views.send_chat_message, name='send_chat_message'),
]
