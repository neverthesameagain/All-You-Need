from django import forms
from django.contrib.auth.models import User
from .models import Article, Comment, Profile, Community, Tag, Event, EventParticipant, ResourceCategory, Resource, ResourceComment, StudyRoom, StudySession
from django.utils import timezone

class ArticleForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select relevant tags for your article"
    )
    
    class Meta:
        model = Article
        fields = ['title', 'content', 'tags']

class CommentForm(forms.ModelForm):
    # Hidden field for parent comment id (for threaded comments)
    parent_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your comment here...'}),
        }

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'bio', 
            'profile_picture',
            'expertise_level',
            'github_url',
            'linkedin_url',
            'website_url',
            'location',
            'interests',
            'is_mentor',
            'mentor_topics'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'expertise_level': forms.Select(attrs={'class': 'form-select'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/username'}),
            'linkedin_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/username'}),
            'website_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, Country'}),
            'interests': forms.CheckboxSelectMultiple(),
            'is_mentor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mentor_topics': forms.Textarea(attrs={
                'rows': 4, 
                'class': 'form-control',
                'placeholder': 'List the topics you can mentor others in (e.g., Data Structures, Algorithms, System Design)'
            })
        }
        help_texts = {
            'is_mentor': 'Check this if you want to mentor other users',
            'mentor_topics': 'Only required if you want to be a mentor',
            'interests': 'Select topics you are interested in or want to learn about',
            'expertise_level': 'Your overall proficiency level in DSA'
        }

class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ['name', 'description']

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'description']
        
    def clean_name(self):
        name = self.cleaned_data['name']
        # Convert to lowercase and replace spaces with hyphens for slug
        from django.utils.text import slugify
        slug = slugify(name)
        
        # Check if a tag with this slug already exists
        if Tag.objects.filter(slug=slug).exists() and (self.instance.pk is None or 
                                                      Tag.objects.get(slug=slug).pk != self.instance.pk):
            raise forms.ValidationError("A tag with this name already exists.")
        
        return name
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Generate slug from name
        from django.utils.text import slugify
        instance.slug = slugify(instance.name)
        
        if commit:
            instance.save()
        
        return instance

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title',
            'description',
            'event_type',
            'start_time',
            'end_time',
            'location',
            'is_online',
            'max_participants',
            'prerequisites',
            'tags',
            'community'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'is_online': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-control'}),
            'prerequisites': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tags': forms.CheckboxSelectMultiple(),
            'community': forms.Select(attrs={'class': 'form-select'})
        }
        help_texts = {
            'location': 'For online events, provide the meeting link',
            'prerequisites': 'List any requirements or preparations needed for the event',
            'max_participants': 'Leave blank for unlimited participants'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError("End time must be after start time")
            
            if start_time < timezone.now():
                raise forms.ValidationError("Start time cannot be in the past")
        
        return cleaned_data

class EventParticipantForm(forms.ModelForm):
    class Meta:
        model = EventParticipant
        fields = ['role', 'feedback', 'rating']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 5,
                'type': 'number'
            })
        }
        help_texts = {
            'rating': 'Rate this event from 1 to 5 stars',
            'feedback': 'Share your thoughts about the event'
        }

class ResourceCategoryForm(forms.ModelForm):
    class Meta:
        model = ResourceCategory
        fields = ['name', 'description', 'category_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter topic name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter topic description'
            }),
            'category_type': forms.HiddenInput()
        }
        help_texts = {
            'name': 'Choose a clear, descriptive name for the topic.',
            'description': 'Provide a brief description of what this topic covers.'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        category_type = cleaned_data.get('category_type')
        
        if not category_type:
            raise forms.ValidationError('Please select a category type.')
        
        # Convert to lowercase and replace spaces with hyphens for slug
        from django.utils.text import slugify
        slug = slugify(name)
        
        # Check if a category with this name already exists in the same category type
        if ResourceCategory.objects.filter(
            slug=slug, 
            category_type=category_type
        ).exists():
            raise forms.ValidationError("A topic with this name already exists in this category.")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Generate slug from name
        from django.utils.text import slugify
        instance.slug = slugify(instance.name)
        
        if commit:
            instance.save()
        
        return instance

class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            'title',
            'description',
            'content',
            'resource_type',
            'difficulty',
            'url',
            'category',
            'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'resource_type': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'data-type': '{{ instance.category.category_type }}'  # This will be populated in the view
            }),
            'tags': forms.CheckboxSelectMultiple()
        }
        help_texts = {
            'url': 'External resource URL (optional if providing content directly)',
            'content': 'Content for self-hosted resources (optional if providing URL)',
            'tags': 'Select relevant tags for better discoverability'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update category choices with proper data-type attributes
        category_field = self.fields['category']
        category_field.widget.attrs['class'] = 'form-select'
        
        # Get all categories and group them by type
        categories = ResourceCategory.objects.all()
        choices = [('', '---------')]  # Add empty choice
        
        # Add IOC categories
        ioc_categories = categories.filter(category_type='ioc')
        if ioc_categories.exists():
            choices.append(('IOC', 'Institute Offered Courses'))
            choices.extend([(c.pk, c.name) for c in ioc_categories])
        
        # Add DNT categories
        dnt_categories = categories.filter(category_type='dnt')
        if dnt_categories.exists():
            choices.append(('DNT', 'Did Not Know That'))
            choices.extend([(c.pk, c.name) for c in dnt_categories])
        
        self.fields['category'].choices = choices

class ResourceCommentForm(forms.ModelForm):
    # Hidden field for parent comment id (for threaded comments)
    parent_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    
    class Meta:
        model = ResourceComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write your comment here...'
            })
        }

class StudyRoomForm(forms.ModelForm):
    class Meta:
        model = StudyRoom
        fields = ['name', 'description', 'room_type', 'course', 'max_members', 'is_private', 'password']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter room name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the purpose of this room'
            }),
            'room_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'course': forms.Select(attrs={
                'class': 'form-select'
            }),
            'max_members': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 2,
                'max': 50
            }),
            'is_private': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room password (if private)'
            })
        }
        help_texts = {
            'name': 'Choose a descriptive name for your study room',
            'description': 'Explain what topics will be studied here',
            'room_type': 'Select the primary purpose of this room',
            'course': 'Select a course (optional)',
            'max_members': 'Maximum number of members (2-50)',
            'is_private': 'Make this room private with password protection',
            'password': 'Required if room is private'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        is_private = cleaned_data.get('is_private')
        password = cleaned_data.get('password')
        
        if is_private and not password:
            raise forms.ValidationError('Password is required for private rooms')
        
        return cleaned_data

class StudySessionForm(forms.ModelForm):
    class Meta:
        model = StudySession
        fields = ['goals']
        widgets = {
            'goals': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What do you want to achieve in this session?'
            })
        }
        help_texts = {
            'goals': 'Set clear goals for this study session'
        }

