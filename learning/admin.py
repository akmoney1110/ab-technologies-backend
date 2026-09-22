from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    Certificate,
    CorporateTrainingRequest,
    Course,
    CourseModule,
    Enrollment,
    Lesson,
    LessonProgress,
    LiveSession,
    Question,
    QuestionOption,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    TrainingCategory,
)


@admin.register(TrainingCategory)
class TrainingCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "instructor",
        "difficulty",
        "course_type",
        "price",
        "is_free",
        "status",
        "is_featured",
    )

    list_filter = (
        "category",
        "difficulty",
        "course_type",
        "status",
        "is_free",
        "is_featured",
    )

    search_fields = (
        "title",
        "description",
        "short_description",
    )

    prepopulated_fields = {
        "slug": ("title",)
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "order",
        "is_published",
    )

    list_filter = (
        "is_published",
        "course",
    )

    search_fields = (
        "title",
        "course__title",
    )


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "lesson_type",
        "duration_minutes",
        "order",
        "is_free_preview",
        "is_published",
    )

    list_filter = (
        "lesson_type",
        "is_free_preview",
        "is_published",
    )

    search_fields = (
        "title",
        "module__title",
        "module__course__title",
    )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "course",
        "status",
        "progress_percentage",
        "enrolled_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "course",
    )

    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "course__title",
    )

    readonly_fields = (
        "enrolled_at",
        "started_at",
        "completed_at",
    )


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "lesson",
        "progress_percentage",
        "completed",
        "updated_at",
    )

    list_filter = (
        "completed",
    )

    search_fields = (
        "enrollment__user__email",
        "lesson__title",
    )


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "lesson",
        "passing_score",
        "max_attempts",
        "is_published",
    )

    list_filter = (
        "is_published",
    )

    search_fields = (
        "title",
        "lesson__title",
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "question",
        "quiz",
        "question_type",
        "points",
        "order",
    )

    list_filter = (
        "question_type",
        "quiz",
    )

    search_fields = (
        "question",
        "quiz__title",
    )


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "question",
        "is_correct",
        "order",
    )

    list_filter = (
        "is_correct",
    )

    search_fields = (
        "text",
        "question__question",
    )


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "quiz",
        "attempt_number",
        "score",
        "status",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "quiz",
    )

    search_fields = (
        "enrollment__user__email",
        "quiz__title",
    )


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_option",
        "is_correct",
        "points_awarded",
    )

    list_filter = (
        "is_correct",
    )


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "scheduled_start",
        "scheduled_end",
        "is_recorded",
    )

    list_filter = (
        "course",
        "is_recorded",
    )

    search_fields = (
        "title",
        "course__title",
    )


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_number",
        "enrollment",
        "issued_at",
        "is_valid",
    )

    list_filter = (
        "is_valid",
    )

    search_fields = (
        "certificate_number",
        "verification_code",
        "enrollment__user__email",
    )

    readonly_fields = (
        "issued_at",
    )


@admin.register(CorporateTrainingRequest)
class CorporateTrainingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "course",
        "number_of_participants",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "course",
    )

    search_fields = (
        "title",
        "organization__name",
        "requested_by__email",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )