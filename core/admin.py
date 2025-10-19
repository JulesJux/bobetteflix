from django.contrib import admin
from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('title', 'movie_id', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('title',)
