import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Post, Comment, Follow, Message, ActivityLog

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def register_user(request):
    if request.method == "POST":
        data = json.loads(request.body)
        if User.objects.filter(username=data['username']).exists():
            return JsonResponse({"error": "Username taken"}, status=400)
        user = User.objects.create_user(username=data['username'], password=data['password'])
        login(request, user)
        ActivityLog.objects.create(user=user, action="joined MiniSocial")
        return JsonResponse({"message": "Registered successfully", "username": user.username})

@csrf_exempt
def login_user(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user = authenticate(username=data['username'], password=data['password'])
        if user is not None:
            login(request, user)
            ActivityLog.objects.create(user=user, action="logged in")
            return JsonResponse({"message": "Logged in", "username": user.username})
        return JsonResponse({"error": "Invalid credentials"}, status=400)

# CLEAN UNIFIED POSTS VIEW
@csrf_exempt
def post_list_create(request):
    if request.method == 'GET':
        posts = Post.objects.all().order_by('-created_at')
        posts_data = []
        for p in posts:
            image_url = None
            if p.image:
                image_url = request.build_absolute_uri(p.image.url)

            # Check if current authenticated user liked this post safely
            is_liked = False
            likes_count = 0
            
            if hasattr(p, 'likes'):
                likes_count = p.likes.count()
                if request.user.is_authenticated:
                    is_liked = p.likes.filter(id=request.user.id).exists()

            # Clean and safe mapping parsing for comments
            comments_list = []
            for c in p.comments.all():
                comments_list.append({
                    'user__username': c.user.username,
                    'content': c.content
                })

            posts_data.append({
                'id': p.id,
                'username': p.user.username,
                'content': p.content if p.content else "", 
                'image_url': image_url, 
                'likes_count': likes_count,
                'is_liked': is_liked,
                'comments': comments_list
            })
        return JsonResponse({'posts': posts_data})

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login required'}, status=401)
            
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image', None)
        
        if not content and not image:
            return JsonResponse({'error': 'Cannot submit an empty post'}, status=400)
            
        post = Post.objects.create(user=request.user, content=content, image=image)
        
        ActivityLog.objects.create(
            user=request.user, 
            action="published a new photo" if image else f"published a new post: '{post.content[:15]}...'"
        )
        
        return JsonResponse({'message': 'Created successfully'}, status=201)

@csrf_exempt
def add_comment(request, post_id):
    if request.method == "POST" and request.user.is_authenticated:
        data = json.loads(request.body)
        post = get_object_or_404(Post, id=post_id)
        comment = Comment.objects.create(post=post, user=request.user, content=data['content'])
        ActivityLog.objects.create(user=request.user, action=f"commented on @{post.user.username}'s post")
        return JsonResponse({"username": request.user.username, "content": comment.content})

@csrf_exempt
def follow_user(request, username):
    if request.method == "POST" and request.user.is_authenticated:
        target_user = get_object_or_404(User, username=username)
        if target_user == request.user:
            return JsonResponse({"error": "You cannot follow yourself"}, status=400)
        
        follow, created = Follow.objects.get_or_create(follower=request.user, following=target_user)
        if not created:
            follow.delete()
            ActivityLog.objects.create(user=request.user, action=f"unfollowed @{username}")
            return JsonResponse({"status": "unfollowed"})
        ActivityLog.objects.create(user=request.user, action=f"started following @{username}")
        return JsonResponse({"status": "followed"})

@csrf_exempt
def get_profile_stats(request):
    if request.user.is_authenticated:
        followers = Follow.objects.filter(following=request.user).values_list('follower__username', flat=True)
        following = Follow.objects.filter(follower=request.user).values_list('following__username', flat=True)
        return JsonResponse({"followers": list(followers), "following": list(following)})
    return JsonResponse({"error": "Not authenticated"}, status=401)

@csrf_exempt
def handle_messages(request, username):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authorized"}, status=401)
    
    other_user = get_object_or_404(User, username=username)
    
    if request.method == "GET":
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(receiver=other_user)) |
            (Q(sender=other_user) & Q(receiver=request.user))
        ).order_by('timestamp')
        
        msg_list = [{"sender": m.sender.username, "text": m.text} for m in messages]
        return JsonResponse({"messages": msg_list})
        
    elif request.method == "POST":
        data = json.loads(request.body)
        msg = Message.objects.create(sender=request.user, receiver=other_user, text=data['text'])
        return JsonResponse({"status": "sent", "text": msg.text})

@csrf_exempt
def get_user_activity(request, username):
    if request.user.is_authenticated:
        target = get_object_or_404(User, username=username)
        logs = ActivityLog.objects.filter(user=target).order_by('-timestamp')[:5]
        return JsonResponse({"activities": [l.action for l in logs]})
    return JsonResponse({"error": "Not authorized"}, status=401)

@csrf_exempt
def delete_post(request, post_id):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'You must be logged in to do that.'}, status=401)
        
        try:
            post = Post.objects.get(id=post_id)
            if post.user == request.user:
                post.delete()
                return JsonResponse({'status': 'deleted'}, status=200)
            else:
                return JsonResponse({'error': 'You do not have permission to delete this post.'}, status=403)
                
        except Post.DoesNotExist:
            return JsonResponse({'error': 'Post not found.'}, status=404)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@csrf_exempt
def password_reset(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            new_password = data.get('new_password')
            
            if not username or not new_password:
                return JsonResponse({'error': 'All fields are required.'}, status=400)
                
            user = User.objects.get(username=username)
            user.set_password(new_password)
            user.save()
            return JsonResponse({'status': 'Password reset successful.'}, status=200)
            
        except User.DoesNotExist:
            return JsonResponse({'error': 'No account associated with that username.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@csrf_exempt
@login_required
def delete_user(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return JsonResponse({'message': 'Account deleted successfully.'}, status=200)
    
    return JsonResponse({'error': 'Invalid request method.'}, status=400)

# Toggle Post Like View Function
@csrf_exempt
def toggle_like(request, post_id):
    if request.method == "POST" and request.user.is_authenticated:
        post = get_object_or_404(Post, id=post_id)
        if hasattr(post, 'likes'):
            if post.likes.filter(id=request.user.id).exists():
                post.likes.remove(request.user)
                status = "unliked"
            else:
                post.likes.add(request.user)
                status = "liked"
                ActivityLog.objects.create(user=request.user, action=f"liked @{post.user.username}'s post")
            return JsonResponse({"status": status, "likes_count": post.likes.count()})
        return JsonResponse({"error": "Likes field missing on Post model"}, status=500)
    return JsonResponse({"error": "Unauthorized"}, status=401)