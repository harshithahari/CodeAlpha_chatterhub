from django.contrib import admin
from django.urls import path
from core import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # CHANGED: Added 'v2/' temporarily to force your browser to load a brand-new page
    path('v2/', views.index, name='index'), 
    path('', views.index, name='index'), # Keeps old path active too
    
    path('api/register/', views.register_user),
    path('api/login/', views.login_user),
   path('api/posts/', views.post_list_create),
    path('api/posts/<int:post_id>/comment/', views.add_comment),
    path('api/users/<str:username>/follow/', views.follow_user),
    path('api/profile/stats/', views.get_profile_stats),
    path('api/chat/<str:username>/', views.handle_messages), 
    path('api/activity/<str:username>/', views.get_user_activity), 
    path('api/posts/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('api/password-reset/', views.password_reset, name='password_reset'),
    path('api/user/delete/', views.delete_user, name='delete_user'),
    path('api/posts/<int:post_id>/like/', views.toggle_like),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)    