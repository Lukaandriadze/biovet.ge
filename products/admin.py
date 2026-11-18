import csv
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.db import models
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Product, Profile


# ==========================================================
# Django Admin-ის სათაური
# ==========================================================

admin.site.site_header = "Biovet – ადმინისტრირება"
admin.site.site_title = "Biovet ადმინი"
admin.site.index_title = "მართვის პანელი"


# ==========================================================
# დამხმარე ფუნქცია სურათის URL-ისთვის
# ==========================================================

def _get_image_url(obj):
    """აბრუნებს სურათის URL-ს (ატვირთული ან გარე ბმული), ან ''-ს."""
    if not obj or not getattr(obj, "pk", None):
        return ""

    image = getattr(obj, "image", None)
    if image:
        try:
            return image.url
        except ValueError:
            pass

    return getattr(obj, "img", "") or ""


# ==========================================================
# ფასის მასობრივი ცვლილება
# ==========================================================

def _price_action(percent):
    factor = Decimal(100 + percent) / Decimal(100)
    sign = "+" if percent > 0 else ""

    @admin.action(description=f"ფასის შეცვლა: {sign}{percent}%")
    def action(modeladmin, request, queryset):
        products = list(queryset)

        for product in products:
            product.price = (product.price * factor).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        Product.objects.bulk_update(products, ["price"])

        modeladmin.message_user(
            request,
            f"{len(products)} პროდუქტის ფასი შეიცვალა ({sign}{percent}%).",
            messages.SUCCESS,
        )

    action.__name__ = f"price_{'plus' if percent > 0 else 'minus'}_{abs(percent)}"
    return action


# ==========================================================
# პროდუქტის ბეჯების მასობრივი ცვლილება
# ==========================================================

def _badge_action(key, text, label):
    @admin.action(description=label)
    def action(modeladmin, request, queryset):
        count = queryset.update(badge=text)

        modeladmin.message_user(
            request,
            f"{count} პროდუქტის ბეჯი განახლდა.",
            messages.SUCCESS,
        )

    action.__name__ = f"badge_{key}"
    return action


# ==========================================================
# პროდუქტის გამოჩენა / დამალვა
# ==========================================================

@admin.action(description="საიტზე გამოჩენა (ჩართვა)")
def make_active(modeladmin, request, queryset):
    count = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f"{count} პროდუქტი ჩანს საიტზე.",
        messages.SUCCESS,
    )


@admin.action(description="საიტიდან დამალვა (გამორთვა)")
def make_inactive(modeladmin, request, queryset):
    count = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f"{count} პროდუქტი დაიმალა.",
        messages.WARNING,
    )


# ==========================================================
# პროდუქტების დუბლირება
# ==========================================================

@admin.action(description="პროდუქტის დუბლირება (ასლის შექმნა)")
def duplicate_products(modeladmin, request, queryset):
    count = 0

    for product in queryset.iterator():
        product.pk = None
        product.id = None
        product._state.adding = True

        product.name = f"{product.name} (ასლი)"
        product.is_active = False

        # თუ created_at არის auto_now_add, Django თავად განაახლებს;
        # თუ არა — აქ შეგვიძლია ხელით განულება, თუ საჭიროა.
        product.save()

        count += 1

    modeladmin.message_user(
        request,
        f"შეიქმნა {count} ასლი. ასლები დამალულია საიტიდან.",
        messages.SUCCESS,
    )


# ==========================================================
# CSV ექსპორტი — Excel-ისთვის
# ==========================================================

@admin.action(description="CSV-ში ექსპორტი (Excel-ისთვის)")
def export_products_csv(modeladmin, request, queryset):
    response = HttpResponse(
        content_type="text/csv; charset=utf-8-sig"
    )
    response["Content-Disposition"] = 'attachment; filename="products.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "ID",
        "დასახელება",
        "კატეგორია",
        "ფასი",
        "ბეჯი",
        "სტატუსი",
        "ჩანს საიტზე",
        "სურათი",
        "აღწერა",
    ])

    products = queryset.select_related("category")

    for product in products.iterator():
        writer.writerow([
            product.id,
            product.name,
            product.category.name if product.category else "",
            product.price,
            product.badge,
            product.status,
            "კი" if product.is_active else "არა",
            _get_image_url(product),
            product.description,
        ])

    return response


# ==========================================================
# პროდუქტის ფორმა
# ==========================================================

class ProductAdminForm(forms.ModelForm):
    img = forms.CharField(
        label="სურათის ბმული",
        required=False,
        max_length=1000,
        widget=forms.TextInput(
            attrs={"style": "width: 40em; max-width: 100%;"}
        ),
        help_text=(
            "მიუთითე გარე სურათის ბმული (https://...) "
            "ან გამოიყენე ქვემოთ მოცემული ატვირთვის ველი."
        ),
    )

    class Meta:
        model = Product
        fields = "__all__"


# ==========================================================
# სურათის ფილტრი
# ==========================================================

class ImageFilter(admin.SimpleListFilter):
    title = "სურათი"
    parameter_name = "has_image"

    def lookups(self, request, model_admin):
        return (
            ("yes", "სურათიანი"),
            ("no", "სურათის გარეშე"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(
                (models.Q(img="") | models.Q(img__isnull=True))
                & (models.Q(image="") | models.Q(image__isnull=True))
            )

        if self.value() == "no":
            return queryset.filter(
                (models.Q(img="") | models.Q(img__isnull=True))
                & (models.Q(image="") | models.Q(image__isnull=True))
            )

        return queryset


# ==========================================================
# პროდუქტის ადმინისტრირება
# ==========================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm

    list_display = (
        "id",
        "thumb",
        "name",
        "category",
        "price",
        "badge",
        "status",
        "is_active",
        "created_at",
    )

    list_display_links = (
        "id",
        "thumb",
        "name",
    )

    list_editable = (
        "price",
        "badge",
        "status",
        "is_active",
    )

    list_filter = (
        "status",
        "is_active",
        "category",
        "badge",
        ImageFilter,
        ("created_at", admin.DateFieldListFilter),
    )

    search_fields = (
        "name",
        "description",
        "category__name",
    )

    list_select_related = ("category",)

    list_per_page = 50
    ordering = ("-id",)
    save_on_top = True
    save_as = True

    readonly_fields = (
        "preview",
        "created_at",
    )

    actions = [
        make_active,
        make_inactive,
        duplicate_products,
        export_products_csv,

        _price_action(5),
        _price_action(10),
        _price_action(20),

        _price_action(-5),
        _price_action(-10),
        _price_action(-20),

        _badge_action("new", "ახალი", "ბეჯი: ახალი"),
        _badge_action("sale", "ფასდაკლება", "ბეჯი: ფასდაკლება"),
        _badge_action("hit", "ჰიტი", "ბეჯი: ჰიტი"),
        _badge_action("clear", "", "ბეჯის წაშლა"),
    ]

    fieldsets = (
        (
            "ძირითადი ინფორმაცია",
            {
                "fields": (
                    "name",
                    "category",
                    "price",
                    "badge",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "აღწერა",
            {
                "fields": ("description",)
            },
        ),
        (
            "სურათი",
            {
                "fields": (
                    "preview",
                    "image",
                    "img",
                )
            },
        ),
        (
            "სისტემური ინფორმაცია",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="სურათი")
    def thumb(self, obj):
        url = _get_image_url(obj)
        if url:
            return format_html(
                '<img src="{}" '
                'style="height:44px;width:44px;'
                'object-fit:contain;border-radius:6px;" '
                'loading="lazy" alt="">',
                url,
            )
        return "—"

    @admin.display(description="მიმდინარე სურათი")
    def preview(self, obj):
        url = _get_image_url(obj)
        if url:
            return format_html(
                '<img src="{}" '
                'style="max-height:200px;max-width:300px;'
                'object-fit:contain;border-radius:8px;" alt="">',
                url,
            )
        return "სურათი არ არის"


# ==========================================================
# მომხმარებელი და პროფილი
# ==========================================================

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    verbose_name_plural = "პროფილი"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    )

    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )


# ==========================================================
# პროფილების ადმინისტრირება
# ==========================================================

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "first_name",
        "last_name",
        "phone",
        "address",
    )

    search_fields = (
        "user__username",
        "user__email",
        "first_name",
        "last_name",
        "phone",
        "address",
    )

    raw_id_fields = ("user",)