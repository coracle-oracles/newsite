from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Event, Order, Role, Shift, ShiftAssignment, TicketType, Transfer, User


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('-start_date',)
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('label', 'event', 'name', 'price', 'max_per_user')
    list_filter = ('event',)
    search_fields = ('label', 'name')
    ordering = ('event', 'name')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('email', 'name')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'password1', 'password2'),
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'owning_user', 'status', 'created_at')
    list_filter = ('ticket_type__event', 'ticket_type', 'status')
    search_fields = ('owning_user__email', 'purchasing_user__email')
    ordering = ('-created_at',)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'from_user', 'to_email', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('from_user__email', 'to_email')
    ordering = ('-created_at',)


class ShiftInline(admin.TabularInline):
    model = Shift
    extra = 1


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'event')
    list_filter = ('event',)
    search_fields = ('name',)
    ordering = ('event', 'name')
    inlines = [ShiftInline]
    filter_horizontal = ('leads',)


class ShiftAssignmentInline(admin.TabularInline):
    model = ShiftAssignment
    extra = 1


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('role', 'start_time', 'end_time', 'capacity', 'spots_remaining')
    list_filter = ('role__event', 'role')
    ordering = ('start_time',)
    inlines = [ShiftAssignmentInline]

    def spots_remaining(self, obj):
        return obj.spots_remaining
    spots_remaining.short_description = 'Spots Remaining'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(role__leads=request.user)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.led_roles.exists()

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.led_roles.exists()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'role' and not request.user.is_superuser:
            kwargs['queryset'] = Role.objects.filter(leads=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'shift', 'created_at')
    list_filter = ('shift__role__event', 'shift__role')
    search_fields = ('user__email', 'user__name')
    ordering = ('shift__start_time',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(shift__role__leads=request.user)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.shift.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.shift.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.led_roles.exists()

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.shift.role.leads.filter(pk=request.user.pk).exists()
        return request.user.led_roles.exists()

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.led_roles.exists()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'shift' and not request.user.is_superuser:
            kwargs['queryset'] = Shift.objects.filter(role__leads=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
