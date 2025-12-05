"""
Custom DRF permissions for fine-grained access control.
"""
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners to edit objects.
    Assumes the model instance has a `seller` or `user` attribute.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for owner
        if hasattr(obj, 'seller'):
            return obj.seller == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class IsSellerOrReadOnly(permissions.BasePermission):
    """
    Permission to only allow sellers to create objects.
    """

    def has_permission(self, request, view):
        # Read permissions allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for authenticated sellers
        return (
            request.user.is_authenticated and
            request.user.user_type == 'seller'
        )


class IsBuyerUser(permissions.BasePermission):
    """
    Permission to only allow buyers.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.user_type == 'buyer'
        )


class IsSellerUser(permissions.BasePermission):
    """
    Permission to only allow sellers.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.user_type == 'seller'
        )


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object.
    """

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
