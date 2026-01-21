from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User, Book, Category, Course, Webinar, Service

class UserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter Full Name',
            'class': 'w-full px-3 sm:px-4 py-2 sm:py-2 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter Email',
            'class': 'w-full px-3 sm:px-4 py-2 sm:py-2 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        initial='buyer',
        widget=forms.HiddenInput()
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter Password',
            'class': 'w-full px-3 sm:px-4 py-2 sm:py-2 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password',
            'class': 'w-full px-3 sm:px-4 py-2 sm:py-2 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'full_name', 'email', 'user_type', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Username',
                'class': 'w-full px-3 sm:px-4 py-2 sm:py-2 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
            })
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.user_type = self.cleaned_data['user_type']
        if commit:
            user.save()
        return user

class UserLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter Email',
            'class': 'w-full px-4 py-3 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter Password',
            'class': 'w-full px-4 py-3 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    remember_me = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            try:
                # Find user by email since they login with email
                user = User.objects.get(email=email)
                username = user.username
            except User.DoesNotExist:
                raise forms.ValidationError('Invalid email or password.')

            # Authenticate with username and password
            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError('Invalid email or password.')
            elif not user.is_active:
                raise forms.ValidationError('This account is disabled.')
            
            cleaned_data['user'] = user

        return cleaned_data

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter Email',
            'class': 'w-full px-4 sm:px-6 py-3 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            return email
        except User.DoesNotExist:
            raise forms.ValidationError('No account found with this email address.')

class VerifyTokenForm(forms.Form):
    token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': '000000',
            'class': 'w-full text-center text-2xl font-bold',
            'maxlength': '6',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_token(self):
        token = self.cleaned_data.get('token')
        if not token or not token.isdigit():
            raise forms.ValidationError('Please enter a valid 6-digit code.')
        
        if self.user:
            from .models import PasswordResetToken
            try:
                reset_token = PasswordResetToken.objects.get(
                    user=self.user,
                    token=token,
                    is_used=False
                )
                if reset_token.is_expired():
                    raise forms.ValidationError('This verification code has expired. Please request a new one.')
                return token
            except PasswordResetToken.DoesNotExist:
                raise forms.ValidationError('Invalid verification code.')
        
        return token

class ResetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password',
            'class': 'w-full px-4 py-3 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'class': 'w-full px-4 py-3 text-sm text-gray-700 bg-[#F9F9F9] border border-gray-300 rounded-lg focus:outline-none focus:border-gray-300'
        })
    )

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('The two passwords do not match.')
            if len(password1) < 8:
                raise forms.ValidationError('Password must be at least 8 characters long.')
        
        return password2


class BookForm(forms.ModelForm):
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter book name',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Enter details',
            'class': 'w-full min-h-[150px] md:min-h-[200px] bg-zinc-50 rounded-md border border-gray-300 p-4 focus:outline-none focus:border-gray-300',
            'rows': 6
        })
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'placeholder': '$$$',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'step': '0.01'
        })
    )

    # Two-tier category selection
    main_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_main_category=True, is_active=True),
        empty_label="Select Main Category",
        widget=forms.Select(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'main-category-select',
            'onchange': 'loadSubcategories(this.value)'
        }),
        help_text="Select the main category for your book"
    )

    subcategory = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'subcategory-input',
            'list': 'subcategory-datalist',
            'placeholder': 'Type or select a sub-category',
            'autocomplete': 'off'
        }),
        help_text="Type a new sub-category or select from existing ones"
    )

    book_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*',
            'id': 'book-image-input'
        })
    )
    book_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': '.zip,.pdf,.epub,.mobi',
            'id': 'book-file-input'
        })
    )

    class Meta:
        model = Book
        fields = ['title', 'description', 'price', 'book_image', 'book_file']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # If editing existing book, pre-populate category fields
        if self.instance and self.instance.pk and self.instance.category:
            if self.instance.category.parent:
                # It's a sub-category
                self.fields['main_category'].initial = self.instance.category.parent
                self.fields['subcategory'].initial = self.instance.category.name
            else:
                # It's a main category (legacy data)
                self.fields['main_category'].initial = self.instance.category
                self.fields['subcategory'].initial = ''

    def clean(self):
        cleaned_data = super().clean()
        main_category = cleaned_data.get('main_category')
        subcategory_name = cleaned_data.get('subcategory', '').strip()

        if not subcategory_name:
            raise forms.ValidationError("Sub-category is required")

        # Normalize subcategory name (capitalize first letter of each word)
        subcategory_name = subcategory_name.title()

        # Check if subcategory exists under this main category (case-insensitive)
        subcategory = Category.objects.filter(
            parent=main_category,
            name__iexact=subcategory_name
        ).first()

        if subcategory:
            # Use existing subcategory
            cleaned_data['category'] = subcategory
        else:
            # Create new subcategory
            subcategory = Category.objects.create(
                name=subcategory_name,
                parent=main_category,
                created_by=self.user,
                is_main_category=False,
                is_active=True,
                approval_status='approved',  # Auto-approve
                is_approved=True
            )
            cleaned_data['category'] = subcategory

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.category = self.cleaned_data['category']

        if commit:
            instance.save()

        return instance

    def clean_book_file(self):
        file = self.cleaned_data.get('book_file')
        if file:
            if file.size > 100 * 1024 * 1024:  # 100MB
                raise forms.ValidationError('File size cannot exceed 100MB.')

            valid_extensions = ['.zip', '.pdf', '.epub', '.mobi']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in valid_extensions:
                raise forms.ValidationError('Only ZIP, PDF, EPUB, and MOBI files are allowed.')
        return file

    def clean_book_image(self):
        image = self.cleaned_data.get('book_image')
        if image:
            if image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image size cannot exceed 10MB.')

            valid_formats = ['jpeg', 'jpg', 'png']
            file_extension = image.name.lower().split('.')[-1]
            if file_extension not in valid_formats:
                raise forms.ValidationError('Only JPEG and PNG images are allowed.')
        return image


class CourseForm(forms.ModelForm):
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter course name',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Enter details',
            'class': 'w-full min-h-[150px] md:min-h-[200px] bg-zinc-50 rounded-md border border-gray-300 p-4 focus:outline-none focus:border-gray-300',
            'rows': 6
        })
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'placeholder': '$$$',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'step': '0.01'
        })
    )

    # Two-tier category selection
    main_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_main_category=True, is_active=True),
        empty_label="Select Main Category",
        widget=forms.Select(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'main-category-select',
            'onchange': 'loadSubcategories(this.value)'
        }),
        help_text="Select the main category for your course"
    )

    subcategory = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'subcategory-input',
            'list': 'subcategory-datalist',
            'placeholder': 'Type or select a sub-category',
            'autocomplete': 'off'
        }),
        help_text="Type a new sub-category or select from existing ones"
    )

    course_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*',
            'id': 'course-image-input'
        })
    )
    course_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': '.zip,.pdf,.mp4,.avi,.mov,.wmv',
            'id': 'course-file-input'
        })
    )

    class Meta:
        model = Course
        fields = ['title', 'description', 'price', 'course_image', 'course_file']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.category:
            if self.instance.category.parent:
                self.fields['main_category'].initial = self.instance.category.parent
                self.fields['subcategory'].initial = self.instance.category.name
            else:
                self.fields['main_category'].initial = self.instance.category
                self.fields['subcategory'].initial = ''

    def clean(self):
        cleaned_data = super().clean()
        main_category = cleaned_data.get('main_category')
        subcategory_name = cleaned_data.get('subcategory', '').strip()

        if not subcategory_name:
            raise forms.ValidationError("Sub-category is required")

        subcategory_name = subcategory_name.title()

        subcategory = Category.objects.filter(
            parent=main_category,
            name__iexact=subcategory_name
        ).first()

        if subcategory:
            cleaned_data['category'] = subcategory
        else:
            subcategory = Category.objects.create(
                name=subcategory_name,
                parent=main_category,
                created_by=self.user,
                is_main_category=False,
                is_active=True,
                approval_status='approved',
                is_approved=True
            )
            cleaned_data['category'] = subcategory

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.category = self.cleaned_data['category']

        if commit:
            instance.save()

        return instance

    def clean_course_file(self):
        file = self.cleaned_data.get('course_file')
        if file:
            if file.size > 500 * 1024 * 1024:  # 500MB for courses (video files)
                raise forms.ValidationError('File size cannot exceed 500MB.')

            valid_extensions = ['.zip', '.pdf', '.mp4', '.avi', '.mov', '.wmv']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in valid_extensions:
                raise forms.ValidationError('Only ZIP, PDF, and video files (MP4, AVI, MOV, WMV) are allowed.')
        return file

    def clean_course_image(self):
        image = self.cleaned_data.get('course_image')
        if image:
            if image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image size cannot exceed 10MB.')

            valid_formats = ['jpeg', 'jpg', 'png']
            file_extension = image.name.lower().split('.')[-1]
            if file_extension not in valid_formats:
                raise forms.ValidationError('Only JPEG and PNG images are allowed.')
        return image


class WebinarForm(forms.ModelForm):
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter webinar name',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Enter details',
            'class': 'w-full min-h-[150px] md:min-h-[200px] bg-zinc-50 rounded-md border border-gray-300 p-4 focus:outline-none focus:border-gray-300',
            'rows': 6
        })
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'placeholder': '$$$',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'step': '0.01'
        })
    )

    # Two-tier category selection
    main_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_main_category=True, is_active=True),
        empty_label="Select Main Category",
        widget=forms.Select(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'main-category-select',
            'onchange': 'loadSubcategories(this.value)'
        }),
        help_text="Select the main category for your webinar"
    )

    subcategory = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'subcategory-input',
            'list': 'subcategory-datalist',
            'placeholder': 'Type or select a sub-category',
            'autocomplete': 'off'
        }),
        help_text="Type a new sub-category or select from existing ones"
    )

    webinar_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*',
            'id': 'webinar-image-input'
        })
    )
    webinar_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': '.zip,.mp4,.avi,.mov,.wmv',
            'id': 'webinar-file-input'
        })
    )

    class Meta:
        model = Webinar
        fields = ['title', 'description', 'price', 'webinar_image', 'webinar_file']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.category:
            if self.instance.category.parent:
                self.fields['main_category'].initial = self.instance.category.parent
                self.fields['subcategory'].initial = self.instance.category.name
            else:
                self.fields['main_category'].initial = self.instance.category
                self.fields['subcategory'].initial = ''

    def clean(self):
        cleaned_data = super().clean()
        main_category = cleaned_data.get('main_category')
        subcategory_name = cleaned_data.get('subcategory', '').strip()

        if not subcategory_name:
            raise forms.ValidationError("Sub-category is required")

        subcategory_name = subcategory_name.title()

        subcategory = Category.objects.filter(
            parent=main_category,
            name__iexact=subcategory_name
        ).first()

        if subcategory:
            cleaned_data['category'] = subcategory
        else:
            subcategory = Category.objects.create(
                name=subcategory_name,
                parent=main_category,
                created_by=self.user,
                is_main_category=False,
                is_active=True,
                approval_status='approved',
                is_approved=True
            )
            cleaned_data['category'] = subcategory

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.category = self.cleaned_data['category']

        if commit:
            instance.save()

        return instance

    def clean_webinar_file(self):
        file = self.cleaned_data.get('webinar_file')
        if file:
            if file.size > 1000 * 1024 * 1024:  # 1GB for webinars (video files)
                raise forms.ValidationError('File size cannot exceed 1GB.')

            valid_extensions = ['.zip', '.mp4', '.avi', '.mov', '.wmv']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in valid_extensions:
                raise forms.ValidationError('Only ZIP and video files (MP4, AVI, MOV, WMV) are allowed.')
        return file

    def clean_webinar_image(self):
        image = self.cleaned_data.get('webinar_image')
        if image:
            if image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image size cannot exceed 10MB.')

            valid_formats = ['jpeg', 'jpg', 'png']
            file_extension = image.name.lower().split('.')[-1]
            if file_extension not in valid_formats:
                raise forms.ValidationError('Only JPEG and PNG images are allowed.')
        return image


class ServiceForm(forms.ModelForm):
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter service name',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Enter service details',
            'class': 'w-full min-h-[150px] md:min-h-[200px] bg-zinc-50 rounded-md border border-gray-300 p-4 focus:outline-none focus:border-gray-300',
            'rows': 6
        })
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'placeholder': '$$$',
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'step': '0.01'
        })
    )

    # Two-tier category selection
    main_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_main_category=True, is_active=True),
        empty_label="Select Main Category",
        widget=forms.Select(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'main-category-select',
            'onchange': 'loadSubcategories(this.value)'
        }),
        help_text="Select the main category for your service"
    )

    subcategory = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full h-11 bg-zinc-50 rounded-md border border-gray-300 px-4 focus:outline-none focus:border-gray-300',
            'id': 'subcategory-input',
            'list': 'subcategory-datalist',
            'placeholder': 'Type or select a sub-category',
            'autocomplete': 'off'
        }),
        help_text="Type a new sub-category or select from existing ones"
    )

    service_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*',
            'id': 'service-image-input'
        })
    )

    class Meta:
        model = Service
        fields = ['title', 'description', 'price', 'service_image']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.category:
            if self.instance.category.parent:
                self.fields['main_category'].initial = self.instance.category.parent
                self.fields['subcategory'].initial = self.instance.category.name
            else:
                self.fields['main_category'].initial = self.instance.category
                self.fields['subcategory'].initial = ''

    def clean(self):
        cleaned_data = super().clean()
        main_category = cleaned_data.get('main_category')
        subcategory_name = cleaned_data.get('subcategory', '').strip()

        if not subcategory_name:
            raise forms.ValidationError("Sub-category is required")

        subcategory_name = subcategory_name.title()

        subcategory = Category.objects.filter(
            parent=main_category,
            name__iexact=subcategory_name
        ).first()

        if subcategory:
            cleaned_data['category'] = subcategory
        else:
            subcategory = Category.objects.create(
                name=subcategory_name,
                parent=main_category,
                created_by=self.user,
                is_main_category=False,
                is_active=True,
                approval_status='approved',
                is_approved=True
            )
            cleaned_data['category'] = subcategory

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.category = self.cleaned_data['category']

        if commit:
            instance.save()

        return instance

    def clean_service_image(self):
        image = self.cleaned_data.get('service_image')
        if image:
            if image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image size cannot exceed 10MB.')

            valid_formats = ['jpeg', 'jpg', 'png']
            file_extension = image.name.lower().split('.')[-1]
            if file_extension not in valid_formats:
                raise forms.ValidationError('Only JPEG and PNG images are allowed.')
        return image