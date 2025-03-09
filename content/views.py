# content/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import models
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q

from .models import (
    Article, Comment, Community, CommunityMembership, Profile, Vote, 
    SavedArticle, Tag, Event, EventParticipant, Resource, ResourceCategory, 
    SavedResource, ResourceComment, StudyRoom, RoomMembership, RoomChat, StudySession, StudyStreak
)
from .forms import (
    ArticleForm, CommentForm, UserForm, ProfileForm, CommunityForm,
    TagForm, EventForm, EventParticipantForm, ResourceForm,
    ResourceCategoryForm, ResourceCommentForm, StudyRoomForm, StudySessionForm
)

# -----------------------------
# Home & Registration Views
# -----------------------------
def home(request):
    """
    Home view: shows articles sorted by newest, oldest, hot, or top.
    Hot sorting combines recency and popularity.
    Allows filtering by tag.
    Also displays upcoming events and active study rooms.
    """
    sort_order = request.GET.get('sort', 'hot')
    tag_slug = request.GET.get('tag', None)
    
    # Base queryset
    articles_queryset = Article.objects.all()
    
    # Filter by tag if specified
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        articles_queryset = articles_queryset.filter(tags=tag)
    
    if sort_order == 'oldest':
        articles = articles_queryset.order_by('created_at')
    elif sort_order == 'top':
        articles = articles_queryset.order_by('-upvotes', 'downvotes', '-created_at')
    elif sort_order == 'hot':
        # Hot sorting: combination of recency and votes
        # For simplicity, we'll just get recent articles and sort them by votes
        import datetime
        
        # Get recent articles (from the last 7 days)
        time_window = timezone.now() - datetime.timedelta(days=7)
        articles = articles_queryset.filter(created_at__gte=time_window).order_by('-upvotes', '-created_at')
        
        # If there are no recent articles, fall back to newest
        if not articles:
            articles = articles_queryset.order_by('-created_at')
    else:  # default to newest
        articles = articles_queryset.order_by('-created_at')
    
    # Get all communities for the sidebar
    communities = Community.objects.all().order_by('name')
    
    # Get popular tags for the sidebar
    popular_tags = Tag.objects.annotate(article_count=models.Count('articles')).order_by('-article_count')[:10]
    
    # Get upcoming events
    upcoming_events = Event.objects.filter(
        start_time__gte=timezone.now(),
        status='upcoming'
    ).order_by('start_time')[:5]
    
    # Get featured resources
    featured_resources = Resource.objects.filter(is_featured=True).order_by('-created_at')[:4]
    
    # Get active study rooms
    active_study_rooms = StudyRoom.objects.filter(
        is_active=True,
        sessions__end_time__isnull=True  # Has an ongoing session
    ).distinct().order_by('-updated_at')[:3]
    
    context = {
        'articles': articles,
        'communities': communities,
        'popular_tags': popular_tags,
        'sort_order': sort_order,
        'current_tag': tag_slug,
        'upcoming_events': upcoming_events,
        'featured_resources': featured_resources,
        'active_study_rooms': active_study_rooms,
    }
    return render(request, 'content/home.html', context)

def register(request):
    """
    Registration view: creates a new user and logs them in.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'content/register.html', {'form': form})

# -----------------------------
# Article Views
# -----------------------------
@login_required
def edit_article(request, pk):
    """
    Edit an existing article.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()  # This saves both the article and the tags (many-to-many)
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm(instance=article)
    return render(request, 'content/edit_article.html', {'form': form, 'article': article})

def article_detail(request, pk):
    """
    Display full details of an article along with its comments.
    Handles comment submissions for logged-in users.
    """
    article = get_object_or_404(Article, pk=pk)
    # Get only top-level comments (no parent)
    comments = article.comments.filter(parent=None).order_by('-created_at')
    form = None
    
    if request.user.is_authenticated:
        if request.method == 'POST':
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.article = article
                comment.user = request.user
                
                # Check if this is a reply to another comment
                parent_id = request.POST.get('parent_id')
                if parent_id:
                    comment.parent = get_object_or_404(Comment, id=parent_id)
                
                comment.save()
                return redirect('article_detail', pk=article.pk)
    else:
        form = CommentForm()
    
    context = {
        'article': article,
        'comments': comments,
        'comment_form': form,
    }
    
    # Check if the article is saved by the current user
    if request.user.is_authenticated:
        is_saved = SavedArticle.objects.filter(
            user_profile=request.user.profile,
            article=article
        ).exists()
        context['is_saved'] = is_saved
    
    return render(request, 'content/article_detail.html', context)

@login_required
def delete_article(request, pk):
    """
    Delete an article.
    """
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        article.delete()
        return redirect('home')
    return render(request, 'content/delete_article.html', {'article': article})

@login_required
def vote_article(request, pk, vote_type):
    """
    Vote on an article (upvote or downvote).
    Uses the Vote model to track votes and prevent duplicate voting.
    Updates user karma.
    """
    article = get_object_or_404(Article, pk=pk)
    
    # Check if user has already voted on this article
    existing_vote = Vote.objects.filter(
        user=request.user,
        content_type='article',
        content_id=article.pk
    ).first()
    
    # If user has already voted the same way, remove their vote
    if existing_vote and existing_vote.vote_type == vote_type:
        if vote_type == 'up':
            article.upvotes = max(0, article.upvotes - 1)
        else:
            article.downvotes = max(0, article.downvotes - 1)
        existing_vote.delete()
    
    # If user has already voted but differently, change their vote
    elif existing_vote:
        if vote_type == 'up':
            article.upvotes += 1
            article.downvotes = max(0, article.downvotes - 1)
            existing_vote.vote_type = 'up'
        else:
            article.downvotes += 1
            article.upvotes = max(0, article.upvotes - 1)
            existing_vote.vote_type = 'down'
        existing_vote.save()
    
    # If user hasn't voted before, add their vote
    else:
        if vote_type == 'up':
            article.upvotes += 1
        else:
            article.downvotes += 1
            
        Vote.objects.create(
            user=request.user,
            content_type='article',
            content_id=article.pk,
            vote_type=vote_type
        )
    
    article.save()
    
    # Update author's karma if profile exists
    try:
        article.author.profile.update_karma()
    except User.profile.RelatedObjectDoesNotExist:
        # Create profile if it doesn't exist
        Profile.objects.create(user=article.author)
        article.author.profile.update_karma()
    
    # Redirect back to the referring page or article detail
    return redirect('article_detail', pk=article.pk)

@login_required
def vote_comment(request, pk, vote_type):
    """
    Vote on a comment (upvote or downvote).
    Uses the Vote model to track votes and prevent duplicate voting.
    Updates user karma.
    """
    comment = get_object_or_404(Comment, pk=pk)
    
    # Check if user has already voted on this comment
    existing_vote = Vote.objects.filter(
        user=request.user,
        content_type='comment',
        content_id=comment.pk
    ).first()
    
    # If user has already voted the same way, remove their vote
    if existing_vote and existing_vote.vote_type == vote_type:
        if vote_type == 'up':
            comment.upvotes = max(0, comment.upvotes - 1)
        else:
            comment.downvotes = max(0, comment.downvotes - 1)
        existing_vote.delete()
    
    # If user has already voted but differently, change their vote
    elif existing_vote:
        if vote_type == 'up':
            comment.upvotes += 1
            comment.downvotes = max(0, comment.downvotes - 1)
            existing_vote.vote_type = 'up'
        else:
            comment.downvotes += 1
            comment.upvotes = max(0, comment.upvotes - 1)
            existing_vote.vote_type = 'down'
        existing_vote.save()
    
    # If user hasn't voted before, add their vote
    else:
        if vote_type == 'up':
            comment.upvotes += 1
        else:
            comment.downvotes += 1
            
        Vote.objects.create(
            user=request.user,
            content_type='comment',
            content_id=comment.pk,
            vote_type=vote_type
        )
    
    comment.save()
    
    # Update comment author's karma if profile exists
    try:
        comment.user.profile.update_karma()
    except User.profile.RelatedObjectDoesNotExist:
        # Create profile if it doesn't exist
        Profile.objects.create(user=comment.user)
        comment.user.profile.update_karma()
    
    # Redirect back to the article detail page
    return redirect('article_detail', pk=comment.article.pk)

# -----------------------------
# User Profile Views
# -----------------------------
@login_required
def dashboard(request):
    """
    User dashboard showing their articles and communities.
    """
    user_articles = Article.objects.filter(author=request.user).order_by('-created_at')
    return render(request, 'content/dashboard.html', {'articles': user_articles})

def profile_detail(request, username):
    """
    Public profile view showing user's profile and activity.
    """
    user = get_object_or_404(User, username=username)
    return render(request, 'content/profile.html', {'user': user})

@login_required
def profile(request):
    """
    Redirect to the user's profile detail view.
    """
    return redirect('profile_detail', username=request.user.username)

@login_required
def edit_profile(request):
    """
    Edit profile view.
    """
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(
            request.POST, 
            request.FILES, 
            instance=request.user.profile
        )
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile = profile_form.save(commit=False)
            
            # Only set mentor_topics if user is a mentor
            if not profile.is_mentor:
                profile.mentor_topics = ''
            
            profile.save()
            profile_form.save_m2m()  # Save many-to-many relationships (interests)
            
            return redirect('profile_detail', username=request.user.username)
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)
    
    return render(request, 'content/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

# -----------------------------
# Community Views
# -----------------------------
def community_list(request):
    """
    List all communities.
    """
    communities = Community.objects.all().order_by('name')
    user_communities = []
    if request.user.is_authenticated:
        user_communities = request.user.joined_communities.all()
    
    context = {
        'communities': communities,
        'user_communities': user_communities,
    }
    return render(request, 'content/community_list.html', context)

def community_detail(request, pk):
    """
    Display details of a community and its articles.
    Supports sorting by newest, oldest, and top (by votes).
    """
    community = get_object_or_404(Community, pk=pk)
    
    # Get sort parameter from query string
    sort_order = request.GET.get('sort', 'newest')
    
    # Sort articles based on parameter
    if sort_order == 'oldest':
        articles = community.articles.all().order_by('created_at')
    elif sort_order == 'top':
        articles = community.articles.all().order_by('-upvotes', 'downvotes', '-created_at')
    else:  # default to newest
        articles = community.articles.all().order_by('-created_at')
    
    is_member = request.user in community.members.all() if request.user.is_authenticated else False
    is_moderator = request.user in community.moderators.all() if request.user.is_authenticated else False
    
    return render(request, 'content/community_detail.html', {
        'community': community,
        'articles': articles,
        'is_member': is_member,
        'is_moderator': is_moderator,
    })

@login_required
def create_community(request):
    """
    Create a new community and add the creator as a member.
    """
    if request.method == "POST":
        form = CommunityForm(request.POST)
        if form.is_valid():
            community = form.save()
            CommunityMembership.objects.create(user=request.user, community=community)
            return redirect('community_detail', pk=community.id)
    else:
        form = CommunityForm()
    return render(request, 'content/create_community.html', {'form': form})

@login_required
def join_community(request, community_id):
    """
    Join a community.
    """
    community = get_object_or_404(Community, id=community_id)
    CommunityMembership.objects.get_or_create(user=request.user, community=community)
    return redirect('community_detail', pk=community.id)

@login_required
def leave_community(request, community_id):
    """
    Leave a community.
    """
    community = get_object_or_404(Community, id=community_id)
    membership = CommunityMembership.objects.filter(user=request.user, community=community)
    if membership.exists():
        membership.delete()
    return redirect('community_list')

@login_required
def create_article(request, community_id=None):
    """
    Create a new article, optionally within a community.
    """
    if community_id:
        community = get_object_or_404(Community, id=community_id)
    else:
        community = None
        
    if request.method == "POST":
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            if community:
                article.community = community
            article.save()
            # Save the many-to-many relationships
            form.save_m2m()  # This saves the tags
            if community:
                return redirect('community_detail', pk=community.id)
            else:
                return redirect('home')
    else:
        form = ArticleForm()
    
    context = {'form': form}
    if community:
        context['community'] = community
    
    return render(request, 'content/create_article.html', context)

@login_required
def save_article(request, pk):
    """
    Save or unsave an article for the current user.
    Acts as a toggle - if already saved, it will unsave.
    """
    article = get_object_or_404(Article, pk=pk)
    
    # Get or create user profile
    try:
        profile = request.user.profile
    except User.profile.RelatedObjectDoesNotExist:
        profile = Profile.objects.create(user=request.user)
    
    # Check if article is already saved
    saved = SavedArticle.objects.filter(user_profile=profile, article=article).exists()
    
    if saved:
        # If already saved, unsave it
        SavedArticle.objects.filter(user_profile=profile, article=article).delete()
    else:
        # If not saved, save it
        SavedArticle.objects.create(user_profile=profile, article=article)
    
    # Redirect back to the referring page or article detail
    next_url = request.GET.get('next', None)
    if next_url:
        return redirect(next_url)
    return redirect('article_detail', pk=article.pk)

# -----------------------------
# Tag Views
# -----------------------------
@login_required
def tag_list(request):
    """
    Display a list of all tags.
    """
    tags = Tag.objects.all()
    return render(request, 'content/tag_list.html', {'tags': tags})

@login_required
def create_tag(request):
    """
    Create a new tag.
    """
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tag_list')
    else:
        form = TagForm()
    
    return render(request, 'content/create_tag.html', {'form': form})

@login_required
def edit_tag(request, slug):
    """
    Edit an existing tag.
    """
    tag = get_object_or_404(Tag, slug=slug)
    
    if request.method == 'POST':
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            return redirect('tag_list')
    else:
        form = TagForm(instance=tag)
    
    return render(request, 'content/edit_tag.html', {'form': form, 'tag': tag})

def tag_detail(request, slug):
    """
    Display articles with a specific tag.
    """
    tag = get_object_or_404(Tag, slug=slug)
    articles = tag.articles.all().order_by('-created_at')
    
    return render(request, 'content/tag_detail.html', {
        'tag': tag,
        'articles': articles
    })

# -----------------------------
# Event Views
# -----------------------------
@login_required
def event_list(request):
    """
    Display list of events with filtering and sorting options.
    """
    event_type = request.GET.get('type', None)
    status = request.GET.get('status', None)
    community_id = request.GET.get('community', None)
    
    # Base queryset
    events = Event.objects.all()
    
    # Apply filters
    if event_type:
        events = events.filter(event_type=event_type)
    if status:
        events = events.filter(status=status)
    if community_id:
        events = events.filter(community_id=community_id)
    
    # Update status of all filtered events
    for event in events:
        event.update_status()
    
    # Get user's events with participant info
    if request.user.is_authenticated:
        user_events = []
        for event in Event.objects.filter(participants__user=request.user).distinct():
            participant = event.participants.get(user=request.user)
            user_events.append({
                'event': event,
                'participant': participant
            })
    else:
        user_events = []
    
    # Get upcoming events
    upcoming_events = events.filter(
        status='upcoming'
    ).order_by('start_time')[:5]
    
    context = {
        'events': events.order_by('start_time'),
        'user_events': user_events,
        'upcoming_events': upcoming_events,
        'event_types': Event.EVENT_TYPES,
        'status_choices': Event.STATUS_CHOICES,
    }
    return render(request, 'content/event_list.html', context)

@login_required
def create_event(request):
    """
    Create a new event.
    """
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            form.save_m2m()  # Save tags
            
            # Add organizer as participant with organizer role
            EventParticipant.objects.create(
                event=event,
                user=request.user,
                role='organizer'
            )
            
            return redirect('event_detail', pk=event.pk)
    else:
        form = EventForm()
    
    return render(request, 'content/create_event.html', {'form': form})

@login_required
def edit_event(request, pk):
    """
    Edit an existing event.
    """
    event = get_object_or_404(Event, pk=pk)
    
    # Check if user is organizer
    if request.user != event.organizer:
        return redirect('event_detail', pk=event.pk)
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect('event_detail', pk=event.pk)
    else:
        form = EventForm(instance=event)
    
    return render(request, 'content/edit_event.html', {
        'form': form,
        'event': event
    })

def event_detail(request, pk):
    """
    Display event details and handle participant registration.
    """
    event = get_object_or_404(Event, pk=pk)
    event.update_status()
    
    # Get participant info if user is registered
    participant = None
    if request.user.is_authenticated:
        participant = EventParticipant.objects.filter(
            event=event,
            user=request.user
        ).first()
    
    # Get all participants
    participants = event.participants.all().select_related('user')
    
    context = {
        'event': event,
        'participant': participant,
        'participants': participants,
        'is_organizer': request.user == event.organizer,
    }
    return render(request, 'content/event_detail.html', context)

@login_required
def join_event(request, pk):
    """
    Register user for an event.
    """
    event = get_object_or_404(Event, pk=pk)
    
    # Check if event is full
    if event.is_full:
        messages.error(request, "This event is already full.")
        return redirect('event_detail', pk=event.pk)
    
    # Check if event is upcoming
    if event.status != 'upcoming':
        messages.error(request, "You can only join upcoming events.")
        return redirect('event_detail', pk=event.pk)
    
    # Register user
    EventParticipant.objects.get_or_create(
        event=event,
        user=request.user,
        defaults={'role': 'attendee'}
    )
    
    return redirect('event_detail', pk=event.pk)

@login_required
def leave_event(request, pk):
    """
    Remove user's registration from an event.
    """
    event = get_object_or_404(Event, pk=pk)
    
    # Check if event is upcoming
    if event.status != 'upcoming':
        messages.error(request, "You can only leave upcoming events.")
        return redirect('event_detail', pk=event.pk)
    
    # Remove registration
    EventParticipant.objects.filter(
        event=event,
        user=request.user
    ).delete()
    
    return redirect('event_detail', pk=event.pk)

@login_required
def cancel_event(request, pk):
    """
    Cancel an event (organizer only).
    """
    event = get_object_or_404(Event, pk=pk)
    
    # Check if user is organizer
    if request.user != event.organizer:
        return redirect('event_detail', pk=event.pk)
    
    if request.method == 'POST':
        event.status = 'cancelled'
        event.save()
        messages.success(request, "Event has been cancelled.")
        return redirect('event_list')
    
    return render(request, 'content/cancel_event.html', {'event': event})

@login_required
def submit_feedback(request, pk):
    """
    Submit feedback and rating for an event.
    """
    event = get_object_or_404(Event, pk=pk)
    participant = get_object_or_404(EventParticipant, event=event, user=request.user)
    
    if request.method == 'POST':
        form = EventParticipantForm(request.POST, instance=participant)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your feedback!")
            return redirect('event_detail', pk=event.pk)
    else:
        form = EventParticipantForm(instance=participant)
    
    return render(request, 'content/submit_feedback.html', {
        'form': form,
        'event': event
    })

# -----------------------------
# Resource Library Views
# -----------------------------
@login_required
def create_category(request):
    """
    Create a new resource category (topic).
    """
    if request.method == 'POST':
        # Get category_type from POST data
        category_type = request.POST.get('category_type')
        if not category_type:
            form = ResourceCategoryForm()
            form.add_error('category_type', 'Please select a category type.')
            return render(request, 'content/create_category.html', {'form': form})
        
        # Create form with POST data
        form = ResourceCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            if request.headers.get('HX-Request'):  # If it's an HTMX request
                return JsonResponse({
                    'id': category.id,
                    'name': category.name,
                    'type': category.category_type
                })
            messages.success(request, f'Topic "{category.name}" has been created successfully.')
            return redirect('resource_list')
    else:
        form = ResourceCategoryForm()
    
    return render(request, 'content/create_category.html', {'form': form})

@login_required
def create_resource(request):
    """
    Create a new resource.
    """
    if request.method == 'POST':
        form = ResourceForm(request.POST)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.author = request.user
            resource.save()
            form.save_m2m()  # Save tags
            return redirect('resource_detail', pk=resource.pk)
    else:
        form = ResourceForm()
    
    # Get categories grouped by type
    categories = {
        'ioc': ResourceCategory.objects.filter(category_type='ioc'),
        'dnt': ResourceCategory.objects.filter(category_type='dnt')
    }
    
    return render(request, 'content/create_resource.html', {
        'form': form,
        'categories': categories
    })

def resource_list(request):
    """
    Display list of resources with filtering and sorting options.
    """
    resource_type = request.GET.get('type', None)
    difficulty = request.GET.get('difficulty', None)
    category_type = request.GET.get('category_type', None)
    category_slug = request.GET.get('category', None)
    sort_order = request.GET.get('sort', 'newest')
    tag_slug = request.GET.get('tag', None)
    
    # Base queryset
    resources = Resource.objects.all()
    
    # Apply filters
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    if difficulty:
        resources = resources.filter(difficulty=difficulty)
    if category_type:
        resources = resources.filter(category__category_type=category_type)
    if category_slug:
        resources = resources.filter(category__slug=category_slug)
    if tag_slug:
        resources = resources.filter(tags__slug=tag_slug)
    
    # Apply sorting
    if sort_order == 'oldest':
        resources = resources.order_by('created_at')
    elif sort_order == 'top':
        resources = resources.order_by('-upvotes', 'downvotes', '-created_at')
    else:  # default to newest
        resources = resources.order_by('-created_at')
    
    # Get categories grouped by type
    categories = {
        'ioc': ResourceCategory.objects.filter(category_type='ioc'),
        'dnt': ResourceCategory.objects.filter(category_type='dnt')
    }
    
    # Get popular tags
    popular_tags = Tag.objects.annotate(
        resource_count=models.Count('resources')
    ).order_by('-resource_count')[:10]
    
    context = {
        'resources': resources,
        'categories': categories,
        'popular_tags': popular_tags,
        'resource_types': Resource.RESOURCE_TYPES,
        'difficulty_levels': Resource.DIFFICULTY_LEVELS,
        'current_type': resource_type,
        'current_difficulty': difficulty,
        'current_category_type': category_type,
        'current_category': category_slug,
        'current_tag': tag_slug,
        'sort_order': sort_order
    }
    return render(request, 'content/resource_list.html', context)

def resource_detail(request, pk):
    """
    Display resource details and handle comments.
    """
    resource = get_object_or_404(Resource, pk=pk)
    comments = resource.comments.filter(parent=None).order_by('-created_at')
    form = None
    
    # Get related resources from the same category
    related_resources = Resource.objects.filter(
        category=resource.category
    ).exclude(
        id=resource.id
    )[:5]
    
    if request.user.is_authenticated:
        if request.method == 'POST':
            form = ResourceCommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.resource = resource
                comment.user = request.user
                
                # Check if this is a reply
                parent_id = request.POST.get('parent_id')
                if parent_id:
                    comment.parent = get_object_or_404(ResourceComment, id=parent_id)
                
                comment.save()
                return redirect('resource_detail', pk=resource.pk)
        else:
            form = ResourceCommentForm()
    
    context = {
        'resource': resource,
        'comments': comments,
        'comment_form': form,
        'related_resources': related_resources
    }
    
    # Check if resource is saved by current user
    if request.user.is_authenticated:
        # Get or create user profile
        try:
            profile = request.user.profile
        except User.profile.RelatedObjectDoesNotExist:
            profile = Profile.objects.create(user=request.user)
            
        is_saved = SavedResource.objects.filter(
            user_profile=profile,
            resource=resource
        ).exists()
        context['is_saved'] = is_saved
    
    return render(request, 'content/resource_detail.html', context)

@login_required
def edit_resource(request, pk):
    """
    Edit an existing resource.
    """
    resource = get_object_or_404(Resource, pk=pk)
    
    # Check if user is author
    if request.user != resource.author:
        return redirect('resource_detail', pk=resource.pk)
    
    if request.method == 'POST':
        form = ResourceForm(request.POST, instance=resource)
        if form.is_valid():
            form.save()
            return redirect('resource_detail', pk=resource.pk)
    else:
        form = ResourceForm(instance=resource)
    
    return render(request, 'content/edit_resource.html', {
        'form': form,
        'resource': resource
    })

@login_required
def delete_resource(request, pk):
    """
    Delete a resource.
    """
    resource = get_object_or_404(Resource, pk=pk)
    
    # Check if user is author
    if request.user != resource.author:
        return redirect('resource_detail', pk=resource.pk)
    
    if request.method == 'POST':
        resource.delete()
        return redirect('resource_list')
    
    return render(request, 'content/delete_resource.html', {'resource': resource})

@login_required
def save_resource(request, pk):
    """
    Save or unsave a resource.
    """
    resource = get_object_or_404(Resource, pk=pk)
    
    # Get or create user profile
    try:
        profile = request.user.profile
    except User.profile.RelatedObjectDoesNotExist:
        profile = Profile.objects.create(user=request.user)
    
    # Check if resource is already saved
    saved = SavedResource.objects.filter(
        user_profile=profile,
        resource=resource
    ).exists()
    
    if saved:
        # If already saved, unsave it
        SavedResource.objects.filter(
            user_profile=profile,
            resource=resource
        ).delete()
    else:
        # If not saved, save it
        SavedResource.objects.create(
            user_profile=profile,
            resource=resource
        )
    
    # Redirect back to the referring page or resource detail
    next_url = request.GET.get('next', None)
    if next_url:
        return redirect(next_url)
    return redirect('resource_detail', pk=resource.pk)

@login_required
def vote_resource(request, pk, vote_type):
    """
    Vote on a resource.
    """
    resource = get_object_or_404(Resource, pk=pk)
    
    # Check if user has already voted
    existing_vote = Vote.objects.filter(
        user=request.user,
        content_type='resource',
        content_id=resource.pk
    ).first()
    
    # If user has already voted the same way, remove their vote
    if existing_vote and existing_vote.vote_type == vote_type:
        if vote_type == 'up':
            resource.upvotes = max(0, resource.upvotes - 1)
        else:
            resource.downvotes = max(0, resource.downvotes - 1)
        existing_vote.delete()
    
    # If user has already voted but differently, change their vote
    elif existing_vote:
        if vote_type == 'up':
            resource.upvotes += 1
            resource.downvotes = max(0, resource.downvotes - 1)
            existing_vote.vote_type = 'up'
        else:
            resource.downvotes += 1
            resource.upvotes = max(0, resource.upvotes - 1)
            existing_vote.vote_type = 'down'
        existing_vote.save()
    
    # If user hasn't voted before, add their vote
    else:
        if vote_type == 'up':
            resource.upvotes += 1
        else:
            resource.downvotes += 1
        
        Vote.objects.create(
            user=request.user,
            content_type='resource',
            content_id=resource.pk,
            vote_type=vote_type
        )
    
    resource.save()
    
    # Update author's karma
    try:
        resource.author.profile.update_karma()
    except User.profile.RelatedObjectDoesNotExist:
        Profile.objects.create(user=resource.author)
        resource.author.profile.update_karma()
    
    return redirect('resource_detail', pk=resource.pk)

@login_required
def edit_category(request, slug):
    """
    Edit an existing resource category.
    """
    category = get_object_or_404(ResourceCategory, slug=slug)
    
    if request.method == 'POST':
        form = ResourceCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('resource_list')
    else:
        form = ResourceCategoryForm(instance=category)
    
    return render(request, 'content/edit_category.html', {
        'form': form,
        'category': category
    })

@login_required
def vote_resource_comment(request, pk, vote_type):
    """
    Vote on a resource comment (upvote or downvote).
    Uses the Vote model to track votes and prevent duplicate voting.
    Updates user karma.
    """
    comment = get_object_or_404(ResourceComment, pk=pk)
    
    # Check if user has already voted
    existing_vote = Vote.objects.filter(
        user=request.user,
        content_type='resource_comment',
        content_id=comment.pk
    ).first()
    
    # If user has already voted the same way, remove their vote
    if existing_vote and existing_vote.vote_type == vote_type:
        if vote_type == 'up':
            comment.upvotes = max(0, comment.upvotes - 1)
        else:
            comment.downvotes = max(0, comment.downvotes - 1)
        existing_vote.delete()
    
    # If user has already voted but differently, change their vote
    elif existing_vote:
        if vote_type == 'up':
            comment.upvotes += 1
            comment.downvotes = max(0, comment.downvotes - 1)
            existing_vote.vote_type = 'up'
        else:
            comment.downvotes += 1
            comment.upvotes = max(0, comment.upvotes - 1)
            existing_vote.vote_type = 'down'
        existing_vote.save()
    
    # If user hasn't voted before, add their vote
    else:
        if vote_type == 'up':
            comment.upvotes += 1
        else:
            comment.downvotes += 1
        
        Vote.objects.create(
            user=request.user,
            content_type='resource_comment',
            content_id=comment.pk,
            vote_type=vote_type
        )
    
    comment.save()
    
    # Update comment author's karma
    try:
        comment.user.profile.update_karma()
    except User.profile.RelatedObjectDoesNotExist:
        Profile.objects.create(user=comment.user)
        comment.user.profile.update_karma()
    
    return redirect('resource_detail', pk=comment.resource.pk)

@login_required
def study_room_list(request):
    """
    Display list of study rooms with filtering options
    """
    room_type = request.GET.get('type')
    course = request.GET.get('course')
    query = request.GET.get('q')
    
    rooms = StudyRoom.objects.filter(is_active=True)
    
    if room_type:
        rooms = rooms.filter(room_type=room_type)
    if course:
        rooms = rooms.filter(course__slug=course)
    if query:
        rooms = rooms.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Get user's joined rooms
    if request.user.is_authenticated:
        joined_rooms = request.user.joined_rooms.all()
    else:
        joined_rooms = []
    
    context = {
        'rooms': rooms,
        'joined_rooms': joined_rooms,
        'room_types': StudyRoom.ROOM_TYPES,
        'courses': ResourceCategory.objects.all()
    }
    return render(request, 'content/study/room_list.html', context)

@login_required
def create_study_room(request):
    """
    Create a new study room
    """
    if request.method == 'POST':
        form = StudyRoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.creator = request.user
            room.save()
            
            # Add creator as admin
            RoomMembership.objects.create(
                user=request.user,
                room=room,
                role='admin'
            )
            
            messages.success(request, 'Study room created successfully!')
            return redirect('study_room_detail', pk=room.pk)
    else:
        form = StudyRoomForm()
    
    return render(request, 'content/study/create_room.html', {'form': form})

@login_required
def study_room_detail(request, pk):
    """
    Display study room details and handle chat
    """
    room = get_object_or_404(StudyRoom, pk=pk)
    
    # Check if user is a member
    try:
        membership = RoomMembership.objects.get(user=request.user, room=room)
        is_member = True
        user_role = membership.role
    except RoomMembership.DoesNotExist:
        is_member = False
        user_role = None
    
    # Get active session if any
    active_session = room.sessions.filter(end_time__isnull=True).first()
    
    # Get recent messages
    messages = room.messages.all()[:50]
    
    context = {
        'room': room,
        'is_member': is_member,
        'user_role': user_role,
        'active_session': active_session,
        'messages': messages,
        'members': room.members.all()
    }
    return render(request, 'content/study/room_detail.html', context)

@login_required
def join_study_room(request, pk):
    """
    Join a study room
    """
    room = get_object_or_404(StudyRoom, pk=pk)
    
    # Check if room is full
    if room.members.count() >= room.max_members:
        messages.error(request, 'This room is full!')
        return redirect('study_room_detail', pk=room.pk)
    
    # Check if user is already a member
    if request.user in room.members.all():
        messages.info(request, 'You are already a member of this room.')
        return redirect('study_room_detail', pk=room.pk)
    
    # Check password for private rooms
    if room.is_private:
        password = request.POST.get('password')
        if not password or password != room.password:
            messages.error(request, 'Invalid password for private room.')
            return redirect('study_room_detail', pk=room.pk)
    
    # Add user as member
    RoomMembership.objects.create(
        user=request.user,
        room=room,
        role='member'
    )
    
    # Create system message
    RoomChat.objects.create(
        room=room,
        user=request.user,
        message=f"{request.user.username} joined the room",
        is_system_message=True
    )
    
    messages.success(request, 'Successfully joined the study room!')
    return redirect('study_room_detail', pk=room.pk)

@login_required
def leave_study_room(request, pk):
    """
    Leave a study room
    """
    room = get_object_or_404(StudyRoom, pk=pk)
    
    try:
        membership = RoomMembership.objects.get(user=request.user, room=room)
        
        # Don't allow creator to leave if they're the only admin
        if membership.role == 'admin' and room.creator == request.user:
            admin_count = RoomMembership.objects.filter(room=room, role='admin').count()
            if admin_count == 1:
                messages.error(request, 'As the creator, you cannot leave without assigning another admin.')
                return redirect('study_room_detail', pk=room.pk)
        
        membership.delete()
        
        # Create system message
        RoomChat.objects.create(
            room=room,
            user=request.user,
            message=f"{request.user.username} left the room",
            is_system_message=True
        )
        
        messages.success(request, 'Successfully left the study room.')
    except RoomMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this room.')
    
    return redirect('study_room_list')

@login_required
def start_study_session(request, pk):
    """
    Start a new study session in a room
    """
    room = get_object_or_404(StudyRoom, pk=pk)
    
    # Check if user is a member
    if request.user not in room.members.all():
        messages.error(request, 'You must be a member to start a session.')
        return redirect('study_room_detail', pk=room.pk)
    
    # Check if there's already an active session
    if room.sessions.filter(end_time__isnull=True).exists():
        messages.error(request, 'There is already an active session in this room.')
        return redirect('study_room_detail', pk=room.pk)
    
    if request.method == 'POST':
        form = StudySessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.room = room
            session.started_by = request.user
            session.save()
            
            # Add starter as first participant
            session.participants.add(request.user)
            
            # Create system message
            RoomChat.objects.create(
                room=room,
                user=request.user,
                message=f"Study session started by {request.user.username}",
                is_system_message=True
            )
            
            messages.success(request, 'Study session started!')
            return redirect('study_room_detail', pk=room.pk)
    else:
        form = StudySessionForm()
    
    return render(request, 'content/study/start_session.html', {
        'form': form,
        'room': room
    })

@login_required
def end_study_session(request, pk, session_pk):
    """
    End an active study session
    """
    room = get_object_or_404(StudyRoom, pk=pk)
    session = get_object_or_404(StudySession, pk=session_pk, room=room)
    
    # Only session starter or room admin can end session
    membership = get_object_or_404(RoomMembership, user=request.user, room=room)
    if session.started_by != request.user and membership.role != 'admin':
        messages.error(request, 'Only the session starter or room admin can end the session.')
        return redirect('study_room_detail', pk=room.pk)
    
    session.end_time = timezone.now()
    session.save()
    
    # Update streaks for all participants
    for participant in session.participants.all():
        try:
            streak = participant.study_streak
        except StudyStreak.DoesNotExist:
            streak = StudyStreak.objects.create(user=participant)
        
        streak.update_streak(timezone.now().date())
    
    # Create system message
    RoomChat.objects.create(
        room=room,
        user=request.user,
        message=f"Study session ended by {request.user.username}",
        is_system_message=True
    )
    
    messages.success(request, 'Study session ended successfully!')
    return redirect('study_room_detail', pk=room.pk)

@login_required
def send_chat_message(request, pk):
    """
    Send a chat message in a study room
    """
    if request.method == 'POST':
        room = get_object_or_404(StudyRoom, pk=pk)
        
        # Check if user is a member
        if request.user not in room.members.all():
            return JsonResponse({'error': 'You must be a member to chat'}, status=403)
        
        message = request.POST.get('message')
        if message:
            chat = RoomChat.objects.create(
                room=room,
                user=request.user,
                message=message
            )
            
            return JsonResponse({
                'status': 'success',
                'message': {
                    'id': chat.id,
                    'user': chat.user.username,
                    'message': chat.message,
                    'created_at': chat.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        
    return JsonResponse({'error': 'Invalid request'}, status=400)
