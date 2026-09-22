from django.db import models

# Create your models here.
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TrainingCategory(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Training Category"
        verbose_name_plural = "Training Categories"

    def __str__(self):
        return self.name


class Course(models.Model):

    class Difficulty(models.TextChoices):
        BEGINNER = "BEGINNER", "Beginner"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"
        ALL_LEVELS = "ALL_LEVELS", "All Levels"

    class CourseType(models.TextChoices):
        SELF_PACED = "SELF_PACED", "Self Paced"
        LIVE = "LIVE", "Live Training"
        HYBRID = "HYBRID", "Hybrid"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    category = models.ForeignKey(
        TrainingCategory,
        on_delete=models.PROTECT,
        related_name="courses",
    )

    title = models.CharField(max_length=255)

    slug = models.SlugField(
        max_length=280,
        unique=True,
    )

    short_description = models.CharField(
        max_length=500,
        blank=True,
    )

    description = models.TextField()

    thumbnail = models.ImageField(
        upload_to="learning/courses/",
        blank=True,
        null=True,
    )

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses_taught",
    )

    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.ALL_LEVELS,
    )

    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.SELF_PACED,
    )

    duration_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    is_free = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    is_featured = models.BooleanField(default=False)

    enrollment_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["is_featured"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def module_count(self):
        return self.modules.count()

    @property
    def lesson_count(self):
        return Lesson.objects.filter(
            module__course=self
        ).count()


class CourseModule(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0)

    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "order"],
                name="unique_course_module_order",
            )
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):

    class LessonType(models.TextChoices):
        VIDEO = "VIDEO", "Video"
        ARTICLE = "ARTICLE", "Article"
        DOCUMENT = "DOCUMENT", "Document"
        LIVE = "LIVE", "Live Session"
        QUIZ = "QUIZ", "Quiz"

    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name="lessons",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    lesson_type = models.CharField(
        max_length=20,
        choices=LessonType.choices,
        default=LessonType.VIDEO,
    )

    video_url = models.URLField(
        blank=True,
    )

    content = models.TextField(
        blank=True,
    )

    resource_file = models.FileField(
        upload_to="learning/resources/",
        blank=True,
        null=True,
    )

    duration_minutes = models.PositiveIntegerField(
        default=0,
    )

    order = models.PositiveIntegerField(default=0)

    is_free_preview = models.BooleanField(
        default=False,
    )

    is_published = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "order"],
                name="unique_module_lesson_order",
            )
        ]

    def __str__(self):
        return self.title


class Enrollment(models.Model):

    class Status(models.TextChoices):
        ENROLLED = "ENROLLED", "Enrolled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        SUSPENDED = "SUSPENDED", "Suspended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ENROLLED,
    )

    enrolled_at = models.DateTimeField(
        auto_now_add=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"],
                name="unique_user_course_enrollment",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["course", "status"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.course}"

    def mark_started(self):
        if not self.started_at:
            self.started_at = timezone.now()

        if self.status == self.Status.ENROLLED:
            self.status = self.Status.IN_PROGRESS

        self.save(
            update_fields=[
                "started_at",
                "status",
            ]
        )

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.progress_percentage = 100
        self.completed_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "progress_percentage",
                "completed_at",
            ]
        )


class LessonProgress(models.Model):

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )

    completed = models.BooleanField(default=False)

    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    last_position_seconds = models.PositiveIntegerField(
        default=0,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson__module__order", "lesson__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "lesson"],
                name="unique_enrollment_lesson_progress",
            )
        ]

    def __str__(self):
        return f"{self.enrollment} - {self.lesson}"


class Quiz(models.Model):
    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name="quiz",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    passing_score = models.PositiveIntegerField(
        default=70,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100),
        ],
    )

    max_attempts = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    time_limit_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Question(models.Model):

    class QuestionType(models.TextChoices):
        SINGLE = "SINGLE", "Single Choice"
        MULTIPLE = "MULTIPLE", "Multiple Choice"
        TRUE_FALSE = "TRUE_FALSE", "True / False"

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question = models.TextField()

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE,
    )

    order = models.PositiveIntegerField(default=0)

    points = models.PositiveIntegerField(default=1)

    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.question[:100]


class QuestionOption(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )

    text = models.CharField(max_length=500)

    is_correct = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    attempt_number = models.PositiveIntegerField(
        default=1,
    )

    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "enrollment",
                    "quiz",
                    "attempt_number",
                ],
                name="unique_quiz_attempt_number",
            )
        ]

    def __str__(self):
        return (
            f"{self.enrollment.user} - "
            f"{self.quiz.title} - "
            f"Attempt {self.attempt_number}"
        )


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="quiz_answers",
    )

    selected_option = models.ForeignKey(
        QuestionOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_answers",
    )

    answer_text = models.TextField(
        blank=True,
    )

    is_correct = models.BooleanField(
        default=False,
    )

    points_awarded = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_attempt_question_answer",
            )
        ]


class LiveSession(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="live_sessions",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    meeting_url = models.URLField()

    scheduled_start = models.DateTimeField()

    scheduled_end = models.DateTimeField()

    recording_url = models.URLField(
        blank=True,
    )

    is_recorded = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Certificate(models.Model):
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="certificate",
    )

    certificate_number = models.CharField(
        max_length=100,
        unique=True,
    )

    issued_at = models.DateTimeField(
        default=timezone.now,
    )

    certificate_file = models.FileField(
        upload_to="learning/certificates/",
        blank=True,
        null=True,
    )

    verification_code = models.CharField(
        max_length=100,
        unique=True,
    )

    is_valid = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.certificate_number


class CorporateTrainingRequest(models.Model):

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        REVIEWING = "REVIEWING", "Reviewing"
        QUOTED = "QUOTED", "Quoted"
        APPROVED = "APPROVED", "Approved"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="training_requests",
        null=True,
        blank=True,
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="corporate_training_requests",
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corporate_training_requests",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(
        blank=True,
    )

    number_of_participants = models.PositiveIntegerField(
        default=1,
    )

    preferred_start_date = models.DateField(
        null=True,
        blank=True,
    )

    preferred_end_date = models.DateField(
        null=True,
        blank=True,
    )

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title