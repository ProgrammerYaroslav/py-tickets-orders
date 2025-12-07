from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from cinema.models import (
    Genre,
    Actor,
    CinemaHall,
    Movie,
    MovieSession,
    Ticket,
    Order,
)

# ... (Existing Movie, Actor, Genre, CinemaHall serializers) ...

class MovieSessionSerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    cinema_hall_name = serializers.CharField(source="cinema_hall.name", read_only=True)
    cinema_hall_capacity = serializers.IntegerField(
        source="cinema_hall.capacity", read_only=True
    )

    class Meta:
        model = MovieSession
        fields = (
            "id",
            "show_time",
            "movie_title",
            "cinema_hall_name",
            "cinema_hall_capacity",
        )


class MovieSessionListSerializer(MovieSessionSerializer):
    # Field for the calculated available tickets
    tickets_available = serializers.IntegerField(read_only=True)

    class Meta:
        model = MovieSession
        fields = (
            "id",
            "show_time",
            "movie_title",
            "cinema_hall_name",
            "cinema_hall_capacity",
            "tickets_available",
        )


class TicketSerializer(serializers.ModelSerializer):
    """
    Serializer for listing tickets inside an Order.
    Includes nested movie_session details.
    """
    movie_session = MovieSessionSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "movie_session")


class TicketCreateSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for creating tickets via POST.
    Validates seat availability.
    """
    class Meta:
        model = Ticket
        fields = ("row", "seat", "movie_session")

    def validate(self, attrs):
        data = super(TicketCreateSerializer, self).validate(attrs)
        
        # Validation 1: Check if seat is within hall bounds
        ticket_row = attrs["row"]
        ticket_seat = attrs["seat"]
        movie_session = attrs["movie_session"]
        cinema_hall = movie_session.cinema_hall

        if not (1 <= ticket_row <= cinema_hall.rows):
            raise ValidationError(
                f"row number must be in available range: (1, {cinema_hall.rows})"
            )
        
        if not (1 <= ticket_seat <= cinema_hall.seats_in_row):
            raise ValidationError(
                f"seat number must be in available range: (1, {cinema_hall.seats_in_row})"
            )

        # Validation 2: Check if seat is already taken
        # We filter tickets for this session matching the requested row and seat
        if Ticket.objects.filter(
            movie_session=movie_session, row=ticket_row, seat=ticket_seat
        ).exists():
            raise ValidationError("The ticket for this movie session and seat is already taken.")

        return data


class OrderSerializer(serializers.ModelSerializer):
    # Use TicketSerializer for reading (GET) and TicketCreateSerializer for writing (POST)
    tickets = TicketSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = ("id", "tickets", "created_at")

    def create(self, validated_data):
        # Extract tickets data from the request context (supplied manually in view or via extra field)
        # Note: In a standard ModelSerializer, we usually use a write_only field for input.
        # Here we extract it from initial_data or handle it via a specific input serializer.
        
        # Strategy: We need to override the creation to handle nested ticket objects.
        tickets_data = self.context.get('view').request.data.get('tickets')
        
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            
            for ticket_data in tickets_data:
                # Use the create serializer to validate every ticket before saving
                ticket_serializer = TicketCreateSerializer(data=ticket_data)
                ticket_serializer.is_valid(raise_exception=True)
                ticket_serializer.save(order=order)
                
            return order


class TicketSeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("row", "seat")


class MovieSessionDetailSerializer(MovieSessionSerializer):
    movie = serializers.SerializerMethodField() # Or use MovieSerializer directly if imported
    cinema_hall = serializers.SerializerMethodField() # Or CinemaHallSerializer
    taken_places = TicketSeatSerializer(source="tickets", many=True, read_only=True)

    class Meta:
        model = MovieSession
        fields = ("id", "show_time", "movie", "cinema_hall", "taken_places")

    # Assuming you have MovieSerializer and CinemaHallSerializer defined elsewhere:
    # Use actual serializers here instead of SerializerMethodField for cleaner code
    # if they are available in the scope.
    
    def get_movie(self, obj):
        from cinema.serializers import MovieSerializer # Avoid circular import
        return MovieSerializer(obj.movie).data

    def get_cinema_hall(self, obj):
        from cinema.serializers import CinemaHallSerializer # Avoid circular import
        return CinemaHallSerializer(obj.cinema_hall).data
