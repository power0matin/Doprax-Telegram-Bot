from bot.utils import (
    validate_location,
    validate_os_slug,
    validate_plan,
    validate_provider,
    validate_vm_name,
)


def test_validate_provider():
    assert validate_provider("Hetzner").ok
    assert not validate_provider("Nope").ok


def test_validate_plan():
    assert validate_plan("DO1").ok
    assert not validate_plan("!bad").ok


def test_validate_location():
    assert validate_location("Germany, Frankfurt").ok
    assert not validate_location("x").ok


def test_validate_vm_name():
    assert validate_vm_name("my-vm-1").ok
    assert not validate_vm_name("bad_name").ok  # underscore not allowed
    assert not validate_vm_name("a" * 40).ok


def test_validate_os_slug():
    allowed = ["ubuntu_22_04", "centos_stream_9"]
    assert validate_os_slug("ubuntu_22_04", allowed).ok
    assert not validate_os_slug("debian", allowed).ok
