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

class OrderSerializer(serializers.ModelSerializer):
    # ... existing fields ...

    def validate(self, attrs):
        # Retrieve tickets from initial_data (raw input)
        tickets_data = self.initial_data.get("tickets")

        # 1. Check presence
        if not tickets_data:
            raise serializers.ValidationError(
                {"tickets": "This field is required."}
            )

        # 2. Check type (must be a list)
        if not isinstance(tickets_data, list):
            raise serializers.ValidationError(
                {"tickets": "This field must be a list."}
            )

        # 3. Check emptiness (optional based on spec, but recommended by reviewer)
        if len(tickets_data) == 0:
            raise serializers.ValidationError(
                {"tickets": "Order must contain at least one ticket."}
            )

        return attrs

    def create(self, validated_data):
        # Now it is safe to fetch tickets, as validate() has passed
        tickets_data = self.initial_data.get("tickets")
        
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            for ticket_data in tickets_data:
                TicketCreateSerializer(data=ticket_data).is_valid(raise_exception=True)
                Ticket.objects.create(order=order, **ticket_data)
                # Or use the serializer .save() if preferred
            
            return order
