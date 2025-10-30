from django.db import models

class Rating(models.Model):
    movie_id = models.IntegerField(db_index=True)
    title = models.CharField(max_length=200, blank=True)
    rating = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.movie_id}) = {self.rating}"
