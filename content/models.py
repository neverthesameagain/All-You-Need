from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from ckeditor.fields import RichTextField
from django.utils import timezone
from datetime import timedelta

class Profile(models.Model):
    EXPERTISE_LEVELS = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert')
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    karma = models.IntegerField(default=0)
    saved_articles = models.ManyToManyField('Article', through='SavedArticle', related_name='saved_by')
    
    # New fields
    expertise_level = models.CharField(max_length=20, choices=EXPERTISE_LEVELS, default='beginner')
    github_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    interests = models.ManyToManyField('Tag', related_name='interested_users', blank=True)
    joined_at = models.DateTimeField(auto_now_add=True, null=True)  # Allow null for existing profiles
    last_seen = models.DateTimeField(auto_now=True)
    is_mentor = models.BooleanField(default=False)
    mentor_topics = models.TextField(blank=True, null=True, help_text="Topics you can mentor others in")
    achievements = models.ManyToManyField('Achievement', related_name='users', blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def update_karma(self):
        """Calculate karma based on user's contributions"""
        # Get all articles by this user
        article_upvotes = sum(article.upvotes for article in self.user.articles.all())
        article_downvotes = sum(article.downvotes for article in self.user.articles.all())
        
        # Get all comments by this user
        comments = Comment.objects.filter(user=self.user)
        comment_upvotes = sum(comment.upvotes for comment in comments)
        comment_downvotes = sum(comment.downvotes for comment in comments)
        
        # Calculate total karma
        self.karma = (article_upvotes - article_downvotes) + (comment_upvotes - comment_downvotes)
        self.save()
    
    @property
    def contribution_count(self):
        """Get total number of contributions (articles + comments)"""
        article_count = self.user.articles.count()
        comment_count = Comment.objects.filter(user=self.user).count()
        return article_count + comment_count
    
    @property
    def activity_streak(self):
        """Calculate the user's current activity streak in days"""
        # TODO: Implement streak calculation
        return 0

    def save(self, *args, **kwargs):
        # Set joined_at for new profiles
        if not self.pk and not self.joined_at:
            self.joined_at = timezone.now()
        super().save(*args, **kwargs)

# Signal to create or update Profile when a User is saved
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        instance.profile.save()

class Community(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, through='CommunityMembership', related_name='joined_communities')
    banner_image = models.ImageField(upload_to='community_banners/', blank=True, null=True)
    icon = models.ImageField(upload_to='community_icons/', blank=True, null=True)
    rules = models.TextField(blank=True, null=True)
    moderators = models.ManyToManyField(User, related_name='moderated_communities', blank=True)

    def __str__(self):
        return self.name

class CommunityMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'community')

class Article(models.Model):
    title = models.CharField(max_length=255)
    content = RichTextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='articles')
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField('Tag', related_name='articles', blank=True)
    
    def __str__(self):
        return self.title

    @property
    def net_votes(self):
        return self.upvotes - self.downvotes

    @property
    def top_comment(self):
        return self.comments.all().order_by('-upvotes', 'downvotes').first()

class SavedArticle(models.Model):
    user_profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user_profile', 'article')
        ordering = ['-saved_at']
    
    def __str__(self):
        return f"{self.user_profile.user.username} saved {self.article.title}"

class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.article.title}'

    @property
    def net_votes(self):
        return self.upvotes - self.downvotes

# Track user votes to prevent duplicate voting
class Vote(models.Model):
    VOTE_TYPES = (
        ('up', 'Upvote'),
        ('down', 'Downvote'),
    )
    
    CONTENT_TYPES = (
        ('article', 'Article'),
        ('comment', 'Comment'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES)
    content_id = models.PositiveIntegerField()
    vote_type = models.CharField(max_length=4, choices=VOTE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'content_type', 'content_id')
        
    def __str__(self):
        return f"{self.user.username}'s {self.vote_type} on {self.content_type} {self.content_id}"

class Tag(models.Model):
    """
    Tags for categorizing articles
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return f"/tags/{self.slug}/"
    
    class Meta:
        ordering = ['name']

# Achievement model for gamification
class Achievement(models.Model):
    TYPES = (
        ('karma', 'Karma Milestone'),
        ('articles', 'Articles Published'),
        ('comments', 'Comments Made'),
        ('streak', 'Activity Streak'),
        ('mentor', 'Mentorship'),
        ('custom', 'Custom Achievement')
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=TYPES)
    icon = models.ImageField(upload_to='achievements/', blank=True, null=True)
    points_required = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['points_required', 'name']

class Event(models.Model):
    EVENT_TYPES = (
        ('workshop', 'Workshop'),
        ('contest', 'Coding Contest'),
        ('mentoring', 'Mentoring Session'),
        ('study_group', 'Study Group'),
        ('other', 'Other')
    )
    
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    )
    
    title = models.CharField(max_length=200)
    description = RichTextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=200, help_text="Physical location or meeting link")
    is_online = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    prerequisites = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField(Tag, related_name='events', blank=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    @property
    def participant_count(self):
        return self.participants.count()
    
    @property
    def is_full(self):
        if self.max_participants:
            return self.participant_count >= self.max_participants
        return False
    
    def update_status(self):
        now = timezone.now()
        if self.status != 'cancelled':
            if now < self.start_time:
                self.status = 'upcoming'
            elif self.start_time <= now <= self.end_time:
                self.status = 'ongoing'
            else:
                self.status = 'completed'
            self.save()

class EventParticipant(models.Model):
    ROLE_CHOICES = (
        ('attendee', 'Attendee'),
        ('speaker', 'Speaker'),
        ('mentor', 'Mentor'),
        ('organizer', 'Organizer')
    )
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_participations')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='attendee')
    registered_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)
    feedback = models.TextField(blank=True, null=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    
    class Meta:
        unique_together = ('event', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.role})"

class ResourceCategory(models.Model):
    """
    Categories for organizing learning resources
    """
    CATEGORY_TYPES = (
        ('ioc', 'Institute Offered Courses'),
        ('dnt', 'Did Not Know That')
    )
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category_type = models.CharField(max_length=3, choices=CATEGORY_TYPES, default='ioc')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_category_type_display()} - {self.name}"
    
    class Meta:
        verbose_name_plural = "Resource Categories"
        ordering = ['category_type', 'name']
        unique_together = ['category_type', 'name']

class Resource(models.Model):
    """
    Learning resources like tutorials, articles, code snippets, etc.
    """
    RESOURCE_TYPES = (
        ('tutorial', 'Tutorial'),
        ('article', 'Article'),
        ('video', 'Video'),
        ('code', 'Code Snippet'),
        ('problem', 'Practice Problem'),
        ('book', 'Book'),
        ('course', 'Course'),
        ('tool', 'Tool/Library'),
        ('other', 'Other')
    )
    
    DIFFICULTY_LEVELS = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    )
    
    title = models.CharField(max_length=200)
    description = RichTextField()
    content = RichTextField(null=True, blank=True, help_text="Optional. Use for self-hosted content.")
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS)
    url = models.URLField(null=True, blank=True, help_text="External resource URL")
    category = models.ForeignKey(ResourceCategory, on_delete=models.CASCADE, related_name='resources')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resources')
    tags = models.ManyToManyField(Tag, related_name='resources', blank=True)
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_featured = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    
    @property
    def net_votes(self):
        return self.upvotes - self.downvotes
    
    class Meta:
        ordering = ['-created_at']

class ResourceComment(models.Model):
    """
    Comments on learning resources
    """
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.resource.title}'
    
    @property
    def net_votes(self):
        return self.upvotes - self.downvotes
    
    class Meta:
        ordering = ['-created_at']

class SavedResource(models.Model):
    """
    Track resources saved by users
    """
    user_profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user_profile', 'resource')
        ordering = ['-saved_at']
    
    def __str__(self):
        return f"{self.user_profile.user.username} saved {self.resource.title}"

class StudyRoom(models.Model):
    """
    Virtual rooms where students can join to study together
    """
    ROOM_TYPES = (
        ('general', 'General Study'),
        ('course', 'Course Specific'),
        ('project', 'Project Work'),
        ('interview', 'Interview Prep')
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    members = models.ManyToManyField(User, related_name='joined_rooms', through='RoomMembership')
    course = models.ForeignKey(ResourceCategory, on_delete=models.SET_NULL, null=True, blank=True, 
                             help_text="For course-specific rooms")
    max_members = models.PositiveIntegerField(default=10)
    is_private = models.BooleanField(default=False)
    password = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
    
    class Meta:
        ordering = ['-updated_at']

class RoomMembership(models.Model):
    """
    Tracks user membership in study rooms including roles
    """
    ROLE_CHOICES = (
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin')
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(StudyRoom, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'room']

class StudySession(models.Model):
    """
    Individual study sessions within rooms
    """
    room = models.ForeignKey(StudyRoom, on_delete=models.CASCADE, related_name='sessions')
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='started_sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    goals = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    participants = models.ManyToManyField(User, related_name='participated_sessions')
    
    def save(self, *args, **kwargs):
        if self.end_time and not self.duration:
            self.duration = self.end_time - self.start_time
        super().save(*args, **kwargs)

class RoomChat(models.Model):
    """
    Chat messages within study rooms
    """
    room = models.ForeignKey(StudyRoom, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_system_message = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']

class StudyStreak(models.Model):
    """
    Tracks user's study streaks and achievements
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='study_streak')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_study_date = models.DateField(null=True, blank=True)
    total_study_sessions = models.PositiveIntegerField(default=0)
    total_study_time = models.DurationField(default=timedelta)
    
    def update_streak(self, study_date):
        if not self.last_study_date:
            self.current_streak = 1
        else:
            delta = study_date - self.last_study_date.date()
            if delta.days == 1:  # Consecutive day
                self.current_streak += 1
            elif delta.days > 1:  # Streak broken
                self.current_streak = 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.last_study_date = study_date
        self.total_study_sessions += 1
        self.save()

class StudyMilestone(models.Model):
    """
    Achievements and milestones for study activities
    """
    MILESTONE_TYPES = (
        ('streak', 'Study Streak'),
        ('sessions', 'Study Sessions'),
        ('hours', 'Study Hours'),
        ('collaboration', 'Group Study'),
        ('contribution', 'Community Contribution')
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_milestones')
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPES)
    title = models.CharField(max_length=100)
    description = models.TextField()
    value = models.PositiveIntegerField()  # e.g., number of days/sessions/hours
    achieved_at = models.DateTimeField(auto_now_add=True)
    badge_image = models.ImageField(upload_to='badges/', null=True, blank=True)
    
    class Meta:
        ordering = ['-achieved_at']





