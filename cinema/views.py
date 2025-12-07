from datetime import datetime
from django.db.models import Count, F
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from cinema.models import Genre, Actor, CinemaHall, Movie, MovieSession, Order
from cinema.serializers import (
    MovieSerializer,
    MovieSessionSerializer,
    MovieSessionListSerializer,
    MovieSessionDetailSerializer,
    OrderSerializer,
    # Import other serializers...
)

class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer

    def get_queryset(self):
        """
        Filtering by genres, actors, and title.
        """
        queryset = self.queryset
        
        # Extract params
        title = self.request.query_params.get("title")
        genres = self.request.query_params.get("genres")
        actors = self.request.query_params.get("actors")

        if title:
            queryset = queryset.filter(title__icontains=title)
        
        if genres:
            # Convert string "1,2,3" to list of integers [1, 2, 3]
            genres_ids = [int(str_id) for str_id in genres.split(",")]
            queryset = queryset.filter(genres__id__in=genres_ids)
            
        if actors:
            actors_ids = [int(str_id) for str_id in actors.split(",")]
            queryset = queryset.filter(actors__id__in=actors_ids)

        return queryset.distinct()


class MovieSessionViewSet(viewsets.ModelViewSet):
    queryset = (
        MovieSession.objects.all()
        # Optimization: select related fields to avoid N+1 queries
        .select_related("movie", "cinema_hall")
    )
    serializer_class = MovieSessionSerializer

    def get_serializer_class(self):
        if self.action == "list":
            return MovieSessionListSerializer
        if self.action == "retrieve":
            return MovieSessionDetailSerializer
        return MovieSessionSerializer

    def get_queryset(self):
        """
        Filtering by date and movie id.
        Annotations for available tickets.
        """
        queryset = self.queryset

        date = self.request.query_params.get("date")
        movie_id = self.request.query_params.get("movie")

        if date:
            # Expecting format YYYY-MM-DD
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            queryset = queryset.filter(show_time__date=date_obj)

        if movie_id:
            queryset = queryset.filter(movie_id=movie_id)
        
        if self.action == "list":
            # Annotate with tickets_available
            # available = capacity - count(tickets)
            queryset = queryset.annotate(
                tickets_available=F("cinema_hall__capacity") - Count("tickets")
            )

        return queryset


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = PageNumberPagination # Explicitly set or rely on settings.py

    def get_queryset(self):
        # Filter orders to only show those belonging to the authenticated user
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the logged-in user to the order
        serializer.save(user=self.request.user)
