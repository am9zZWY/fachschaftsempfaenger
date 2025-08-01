import json
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render
from django.utils import timezone

from fachschaftsempfaenger.models import Advertisement, Food, Mastodon, Member, Menu
from . import __author__ as author
from . import __repository_url__ as repo_url
from . import bus, calendar, mastodon, mensa, weather


def sitzung_tile(request):
    ical_url = "https://cloud.fsi.uni-tuebingen.de/remote.php/dav/public-calendars/e8wPTX4TBpCNpb7W?export"

    """
    Naming convention for 'Sitzungen' in the FSI calender is the keyword "Sitzung" lead by either prefix {"FSI"|"FSK"}
    ie. "FSI Sitzung" or "FSK Sitzung"
    
    If necessary titles can be extended by placing additional identifiers between upper keywords.
    ie. "FSI Discord Sitzung"
    although these can mentioned in the location handle as well
    """
    try:
        # event_generator returns sorted event tuplets
        event_generator = calendar.events(ical_url)
        info = None
        kogni = None

        for event in event_generator:
            # item = (date, time, title, location)
            title = str(event[2]).lower().strip()
            if (
                    title.endswith("sitzung")
                    and datetime.strptime(event[0], "%d.%m.%Y").date()
                    >= datetime.today().date()
            ):
                if title.startswith("fsi") and not info:
                    info = dict(date=event[0], time=event[1], location=event[3])
                elif title.startswith("fsk") and not kogni:
                    kogni = dict(date=event[0], time=event[1], location=event[3])
                else:
                    pass
    except:
        info = None
        kogni = None

    return render(request, "tiles/sitzung.html", dict(info=info, kogni=kogni))


def calendar_tile(request):
    ical_urls = [
        "https://cloud.fsi.uni-tuebingen.de/remote.php/dav/public-calendars/e8wPTX4TBpCNpb7W?export",
        "https://eei.fsi.uni-tuebingen.de/calendar.php?allevents",
    ]

    number_events = 5

    try:
        event_generator = calendar.events(ical_urls)
        events = []
        for item in event_generator:
            # only put the item in if it is today or in the future
            if datetime.strptime(item[0], "%d.%m.%Y").date() >= datetime.today().date():
                events.append(item)
        # slice according to number_events
        events = events[:number_events]
    except:
        event_generator = calendar.events(ical_urls)
        events = list(event_generator)  # [:number_events]

    url = "https://cloud.fsi.uni-tuebingen.de/apps/calendar/p/e8wPTX4TBpCNpb7W"
    events = events[:number_events]

    return render(request, "tiles/calendar.html", dict(events=events, link=url))


def bus_tile(request):
    stopid = "de:08416:10252:0:4"
    url = "https://www.swtue.de/abfahrt.html?halt={}".format(stopid)
    events = bus.get_departures(stopid)

    return render(request, "tiles/bus.html", dict(events=events, link=url))


def forecast_tile(request):
    import urllib.request

    response = urllib.request.urlopen(
        "http://api.openweathermap.org/data/2.5/forecast?q=Tuebingen,DE&appid=806b3582a0c4787e47e950a6274b681a&units=metric"
    )
    content = response.read()
    data = json.loads(content.decode("utf-8"))

    today_string = datetime.datetime.now().strftime("%Y-%m-%d")
    tomorrow_string = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    days = dict()
    for d in data["list"]:
        tmp_day = d["dt_txt"][:10]
        if not (tmp_day == today_string or tmp_day == tomorrow_string):
            continue
        if " 09:00" in d["dt_txt"] or " 12:00" in d["dt_txt"] or "18:00" in d["dt_txt"]:
            if tmp_day in days:
                days[tmp_day].append(d)
            else:
                days[tmp_day] = [d]
    if today_string in days:
        days_array = [days[today_string], days[tomorrow_string]]
    else:
        days_array = [days[tomorrow_string]]

    return render(
        request, "tiles/forecast.html", dict(data=days, data_array=days_array)
    )


def weather_tile(request, use_kelvin=False):
    ctx = weather.weather_data()
    ctx["link"] = "https://wetteronline.de/wetter-aktuell/tuebingen"
    return render(request, "tiles/weather.html", ctx)


def mensa_tile(request, mensa_name: str):
    mensa_name_id_map = {
        "morgenstelle": {
            "name": "Mensa Morgenstelle",
            "items": [
                {
                    "type": "mensa",
                    "id": "621",
                    "path": "mensa-morgenstelle-tuebingen",
                },
                {
                    "type": "cafe",
                    "id": "724",
                    "path": "cafeteria-morgenstelle-tuebingen"
                }
            ]
        },
        "wilhelmstrasse": {
            "name": "Mensa Wilhelmstraße",
            "items": [
                {
                    "type": "mensa",
                    "id": "611",
                    "path": "mensa-wilhelmstrasse-tuebingen",
                },
                {
                    "type": "cafe",
                    "id": "715",
                    "path": "cafe-wilhelmstrasse-tuebingen",
                }]
        },
        "prinz_karl": {
            "name": "Mensa Prinz Karl",
            "items": [
                {
                    "type": "mensa",
                    "id": "623",
                    "path": "mensa-prinz-karl-tuebingen",
                }
            ]
        },
    }
    # Get the data from the dictionary
    mensa_data = mensa_name_id_map.get(mensa_name)

    mensa_date = ""
    mensa_website = ""
    all_meals = []
    for item in mensa_data["items"]:

        item_id = item["id"]
        item_json = "https://www.my-stuwe.de/wp-json/mealplans/v1/canteens/{}".format(item_id)
        date_string, meals = mensa.load_data(item_json, item_id)
        all_meals.extend(meals)

        if item["type"] == "mensa":
            mensa_website = "https://www.my-stuwe.de/mensa/{}".format(item["path"])
            mensa_date = date_string

    try:
        context = {
            "meals": all_meals,
            "link": mensa_website,
            "date": mensa_date,
            "name": mensa_data["name"],
        }

    except BaseException as e:
        print("Error retrieving the Mensa plan!", e)
        context = {
            "meals": None,
            "link": mensa_website,
            "date": None,
            "name": mensa_data["name"],
        }

    return render(request, "tiles/mensa.html", context)


def mastodon_tile(request):
    """
    Renders the Mastodon tile which shows the last post of a Mastodon Account provided in the Django
    Administration Backend.
    """

    try:
        account = Mastodon.objects.filter(visible=True).first()

        username = account.username
        instance = account.instance

    except BaseException as e:
        print("Error retrieving the Mastodon account!", e)
        username = None
        instance = None

    if username is None or instance is None:
        username = "fsi_tue"
        instance = "https://toot.kif.rocks"

    profile = instance + "/@" + username

    try:
        toot_id, toot_content, toot_attachment = mastodon.load_data(instance, username)

        context = dict(
            toot_id=toot_id.replace("activity", "embed"),
            toot_content=toot_content,
            toot_attachment=toot_attachment,
            toot_instance=instance,
            link=profile,
        )

    except BaseException as e:
        print("Error retrieving the mastodon toot!", e)
        context = dict(
            toot_id=None,
            toot_content=None,
            toot_attachment=None,
            toot_instance=instance,
            link=profile,
            hidden=True,
        )

    return render(request, "tiles/mastodon.html", context)


def foodtruck_tile(request):
    """
    Renders the tile for the food truck. It queries the models `Menu` and `Food` to aquire a menu for the current week
    (a menu that's either meant for the current day or a day that is at most 6 days into the future).
    If no menu exists for this time period, an exception is thrown and and a `None` object is passed to the template.
    """
    try:
        menu_date = Menu.objects.get(
            date__gte=timezone.now(),
            date__lte=timezone.now() + datetime.timedelta(days=6),
        ).date.strftime("%d.%m.%Y")
        menu = Food.objects.filter(
            menu_item__date__gte=timezone.now(),
            menu_item__date__lte=timezone.now() + datetime.timedelta(days=6),
        )

        context = dict(menu=menu, menu_date=menu_date)
    except ObjectDoesNotExist:
        print("No appropriate food truck items or menus found for the current week!")
        context = dict(menu=None, hidden=True)

    return render(request, "tiles/foodtruck.html", context)


def advertisement_tile(request):
    """
    Renders a custom advertisement message to be displayed.
    """
    # Are there any messages to be displayed right now? If there are, select one at random.
    # Note that this query is quite expensive and could potentially slow the load time of this tile down.
    if Advertisement.objects.filter(
            start_date__lte=timezone.now(), end_date__gte=timezone.now()
    ):
        qs = (
            Advertisement.objects.filter(
                start_date__lte=timezone.now(), end_date__gte=timezone.now()
            )
            .order_by("?")
            .first()
        )
        context = dict(advertisement=qs)
    else:
        print("There are no advertisement messages to be displayed right now!")
        context = dict(advertisement=None, hidden=True)

    return render(request, "tiles/advertisement.html", context)


def fachschaft_tile(request):
    """
    Randomly chooses a picture of a member of the student union
    and displays it alongside their field of study etc.
    """
    # Select one of the people in the database at random and display their details.
    # Note that this query is quite expensive and could potentially slow the load time of this tile down.
    if Member.objects.exists():
        qs = Member.objects.order_by("?").first()
        context = dict(person=qs)
    else:
        print("No people of the student union found in database!")
        context = dict(person=None, hidden=True)

    return render(request, "tiles/fachschaft.html", context)


def index(request):
    """
    The tiles that are displayed on the main page are loaded via JQuery (see index.html file itself)
    Additional data to be displayed (i.e. footer, overlays etc.) can be passed via the context.
    """
    copy = "2018 " + author

    context = dict(author=author, copyright=copy, repo_url=repo_url)

    return render(request, "index.html", context)
