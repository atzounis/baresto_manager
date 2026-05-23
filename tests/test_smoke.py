import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_guest_menu_404(client):
    import uuid

    r = client.get(f"/qr/{uuid.uuid4()}/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_login_page(client):
    r = client.get(reverse("login"))
    assert r.status_code == 200
