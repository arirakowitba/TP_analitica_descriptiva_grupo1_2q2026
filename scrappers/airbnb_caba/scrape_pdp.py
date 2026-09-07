"""
ETAPA 2 — Ficha completa de cada anuncio (PDP).

La página de anuncio carga sus secciones en diferido con un POST a
/api/v3/StaysPdpSections. Los flags "includeGp<X>Fragment" del payload deciden
qué secciones vuelven con cuerpo. Prendiéndolos todos, TODA la ficha llega en
una sola llamada: amenities (con available true/false, o sea también lo que el
anuncio NO tiene), reglas de la casa, check-in/out, política de cancelación,
host con métricas, descripción, arreglo de camas y fotos.

Salidas:
    pdp_raw.jsonl        una línea por anuncio (campos planos)
    amenities_raw.jsonl  tabla larga: un registro por (anuncio, amenity)

Uso:
    python scrape_pdp.py --limit 5      # prueba
    python scrape_pdp.py                # todo, reanudable
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from airbnb_common import (
    API_KEY, CURRENCY, HOST, LOCALE,
    b64, jsonl_append, jsonl_gz_append, jsonl_ids, new_session, polite_sleep,
    unb64,
)

OUT = Path(__file__).parent
SEARCH_RAW = OUT / "search_raw.jsonl"
PDP_RAW = OUT / "pdp_raw.jsonl"
AMEN_RAW = OUT / "amenities_raw.jsonl"
# respuesta cruda comprimida: permite mejorar el parser sin re-scrapear
FULL_RAW = OUT / "pdp_full.jsonl.gz"

PDP_HASH = "f9c50b6a6918e94f6bf33d5163ec65afe0bb0715b72f2d41131d9256d3f785cb"

# Fragmentos "Gp": los prendemos para que la respuesta traiga el cuerpo.
GP = ["AccessibilityFeatures", "AdminBanner", "Amenities", "AvailabilityCalendar",
      "AvailabilityCalendarInline", "Bathroom", "BookIt", "BookItNonExperiencedGuest",
      "CancellationPolicyPickerModal", "Description", "Hero", "HighlightsCompact",
      "Highlights", "HostOverviewDefault", "LocationPdp", "LuxeServices",
      "MarqueeBookItFloatingFooter", "MarqueeBookItNav", "MarqueeBookItSidebar",
      "MeetYourHost", "MessageBanner", "Nav", "NavMobile",
      "NonExperiencedGuestLearnMoreModal", "OverviewV2", "Policies",
      "PropertyAvailableRooms", "ReportToAirbnb", "ReviewsEmpty", "Reviews",
      "ReviewsHighlightBanner", "SeoLinks", "SleepingArrangement",
      "SleepingArrangementImages", "Title", "UgcTranslation"]

MIG = ["AccessibilityFeaturesModal", "AccessibilityFeaturesPreviewCarousel", "Amenities",
       "AvailabilityCalendar", "AvailabilityCalendarInline", "Bathroom",
       "BookItCalendarSheet", "BookItFloatingFooter", "BookItNav",
       "BookItNonExperiencedGuest", "BookItSidebar", "Description", "Hero",
       "HighlightsCompact", "Highlights", "HostOverviewDefault", "LocationPdp",
       "LuxeServices", "MarqueeBookItFloatingFooter", "MarqueeBookItNav",
       "MarqueeBookItSidebar", "MeetYourHost", "MessageBanner", "Nav", "NavMobile",
       "NonExperiencedGuestLearnMoreModal", "OnlyOnBookIt", "OnlyOnBookItNav",
       "OverviewV2", "PdpEducation", "Policies", "PropertyAvailableRooms",
       "ReportToAirbnb", "ReviewsEmpty", "Reviews", "ReviewsHighlightBanner",
       "SeoLinks", "SleepingArrangement", "SleepingArrangementImages", "Title"]


def build_variables(listing_id: str, checkin: str, checkout: str, adults: int) -> dict:
    v = {
        "amenityIds": None, "categoryTag": None, "causeId": None,
        "dateRange": {"startDate": checkin, "endDate": checkout},
        "demandStayListingId": b64(f"DemandStayListing:{listing_id}"),
        "federatedSearchId": None, "federatedSearchSessionId": None,
        "guestCounts": {"numberOfAdults": adults},
        "id": b64(f"StayListing:{listing_id}"),
        "includePdpLayoutPipelineInputs": False,
        "numberOfChildren": None, "numberOfInfants": None, "numberOfPets": None,
        "p3ImpressionId": f"p3_{int(time.time())}_caba",
        "photoId": None,
        "pdpSectionsRequest": {
            "adults": str(adults), "amenityFilters": None, "bypassTargetings": False,
            "categoryTag": None, "causeId": None,
            "checkIn": checkin, "checkOut": checkout,
            "children": None, "directBookingParams": None, "disasterId": None,
            "discountedGuestFeeVersion": None, "federatedSearchId": None,
            "forceBoostPriorityMessageType": None, "hostPreview": False,
            "infants": None, "interactionType": None,
            "layouts": ["SIDEBAR", "SINGLE_COLUMN"],
            "p3ImpressionId": f"p3_{int(time.time())}_caba",
            "partner": None, "partnerProgram": None, "pdpTypeOverride": None,
            "pets": 0, "photoId": None, "preview": False,
            "previousStateCheckIn": None, "previousStateCheckOut": None,
            "priceDropSource": None, "privateBooking": False, "promotionUuid": None,
            "relaxedAmenityIds": None, "searchId": None, "sectionIds": None,
            "selectedCancellationPolicyId": None, "selectedRatePlanId": None,
            "splitStays": None, "staysBookingMigrationEnabled": False,
            "translateUgc": None, "useNewSectionWrapperApi": False,
        },
    }
    for f in GP:
        v[f"includeGp{f}Fragment"] = True
    for f in MIG:
        v[f"includePdpMigration{f}Fragment"] = True
    return v


def fetch_pdp(session, listing_id, checkin, checkout, adults, retries=3):
    url = (f"{HOST}/api/v3/StaysPdpSections/{PDP_HASH}"
           f"?operationName=StaysPdpSections&locale={LOCALE}&currency={CURRENCY}")
    body = {
        "operationName": "StaysPdpSections",
        "variables": build_variables(listing_id, checkin, checkout, adults),
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": PDP_HASH}},
    }
    ultimo = "sin intentos"
    for attempt in range(retries):
        try:
            r = session.post(url, json=body,
                             headers={"X-Airbnb-Api-Key": API_KEY,
                                      "Content-Type": "application/json"},
                             timeout=30)
        except requests.RequestException as e:
            # Un corte de TCP no es un bloqueo, pero antes se llevaba puesta la
            # corrida entera: acá sólo se miraban códigos HTTP, así que un
            # ConnectionResetError salía como excepción y mataba el proceso.
            # Pasó en la primera corrida larga, a los 2.984 anuncios.
            ultimo = f"{type(e).__name__}: {e}"
            time.sleep(4 * (2 ** attempt))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ultimo = f"HTTP {r.status_code}"
            time.sleep(10 * (2 ** attempt))
            continue
        try:
            j = r.json()
        except ValueError:
            # respuesta que no es JSON = desafío de bot o página de error.
            # Devolverlo como fallo (y no como excepción) hace que cuente para
            # el corte por errores encadenados, que es el comportamiento que
            # queremos ante un bloqueo real.
            ultimo = f"respuesta no-JSON (HTTP {r.status_code}, {len(r.content)} bytes)"
            time.sleep(8 * (2 ** attempt))
            continue
        if j.get("errors"):
            return None, j["errors"]
        return j, None
    return None, ultimo


def txt_items(section, key):
    return " | ".join(
        i.get("title", "") for i in (section or {}).get(key, []) or [] if i
    )


def parse(listing_id: str, j: dict):
    sp = (j.get("data") or {}).get("presentation", {}).get("stayProductDetailPage") or {}
    S = sp.get("sections") or {}
    B = {}
    for s in S.get("sections") or []:
        sec = s.get("section")
        if sec and len(sec) > 1:
            B[s.get("sectionComponentType")] = sec

    md = S.get("metadata") or {}
    ed = ((md.get("loggingContext") or {}).get("eventDataLogging")) or {}
    sh = md.get("sharingConfig") or {}

    cal = B.get("AVAILABILITY_CALENDAR_DEFAULT") or {}
    de = B.get("DESCRIPTION_DEFAULT") or {}
    po = B.get("POLICIES_DEFAULT") or {}
    ho = B.get("MEET_YOUR_HOST") or {}
    lo = B.get("LOCATION_PDP") or {}
    hi = B.get("HIGHLIGHTS_DEFAULT") or {}
    ph = B.get("PHOTO_TOUR_SCROLLABLE") or {}
    sl = B.get("SLEEPING_ARRANGEMENT_IMAGES") or {}
    card = ho.get("cardData") or {}

    # REVIEWS_DEFAULT: agregados que ya venían en la respuesta y se tiraban.
    # No trae el texto de las reseñas (eso es otra query), pero sí el reparto
    # de estrellas, el percentil de calidad que calcula Airbnb y los tags
    # sintetizados de lo que mencionan los huéspedes.
    rv = B.get("REVIEWS_DEFAULT") or {}
    dist = {}
    for cr in rv.get("ratingDistribution") or []:
        et = cr.get("label")
        if et:
            dist[str(et)] = cr.get("percentage")
    tags = " | ".join(
        f"{t.get('localizedName')}:{t.get('count')}"
        for t in rv.get("reviewTags") or [] if t.get("localizedName")
    )

    reglas = {}
    for sec in po.get("houseRulesSections") or []:
        reglas[sec.get("title")] = txt_items(sec, "items")

    host_stats = {st.get("type"): st.get("value") for st in card.get("stats") or []}

    rec = {
        "listing_id": listing_id,
        "url": f"{HOST}/rooms/{listing_id}",
        # --- métricas planas (vienen del propio logging de Airbnb) ---
        "room_type": ed.get("roomType"),
        "capacidad": ed.get("personCapacity"),
        "home_tier": ed.get("homeTier"),
        "es_superhost": ed.get("isSuperhost"),
        "reviews_visibles": ed.get("visibleReviewCount"),
        "rating_general": ed.get("guestSatisfactionOverall"),
        "rating_exactitud": ed.get("accuracyRating"),
        "rating_llegada": ed.get("checkinRating"),
        "rating_limpieza": ed.get("cleanlinessRating"),
        "rating_comunicacion": ed.get("communicationRating"),
        "rating_ubicacion": ed.get("locationRating"),
        "rating_precio": ed.get("valueRating"),
        "idioma_descripcion": ed.get("descriptionLanguage"),
        "latitud_pdp": ed.get("listingLat") or lo.get("lat"),
        "longitud_pdp": ed.get("listingLng") or lo.get("lng"),
        "radio_ofuscacion_m": lo.get("mapMarkerRadiusInMeters"),
        # --- ficha ---
        "tipo_propiedad": sh.get("propertyType"),
        "resumen_titulo": sh.get("title"),
        "titulo": (B.get("TITLE_DEFAULT") or {}).get("title"),
        "detalle_items": " | ".join(
            d.get("title", "") for d in cal.get("descriptionItems") or [] if d
        ),
        "capacidad_max": cal.get("maxGuestCapacity"),
        "ubicacion_localizada": cal.get("localizedLocation"),
        "descripcion": ((de.get("htmlDescription") or {}).get("htmlText")),
        "highlights": " | ".join(
            f"{h.get('title')}: {h.get('subtitle')}" for h in hi.get("highlights") or []
        ),
        "cantidad_fotos_pdp": len(ph.get("mediaItems") or []),
        "arreglo_camas": " | ".join(
            f"{a.get('title')}: {a.get('subtitle')}"
            for a in sl.get("arrangementDetails") or []
        ),
        # --- reglas y políticas ---
        "reglas_checkin_checkout": reglas.get("Check-in y check-out"),
        "reglas_estadia": reglas.get("Durante tu estadía"),
        "reglas_adicionales": po.get("additionalHouseRules"),
        "licencia": " | ".join(po.get("propertyLicenseTextList") or []),
        # --- host ---
        "host_nombre": card.get("name"),
        "host_id": (unb64(card["userId"]).split(":")[1]
                    if card.get("userId") else None),
        "host_es_superhost": card.get("isSuperhost"),
        "host_verificado": card.get("isVerified"),
        "host_reviews": host_stats.get("REVIEW_COUNT"),
        "host_rating": host_stats.get("RATING"),
        "host_anios": host_stats.get("TIME_AS_HOST") or host_stats.get("YEARS_HOSTING"),
        "host_detalles": " | ".join(ho.get("hostDetails") or []),
        "host_tiempo_respuesta": ho.get("hostRespondTimeCopy"),
        "host_sobre_mi": ho.get("about"),
        "host_cohosts": len(ho.get("cohosts") or []),
        # --- reviews: agregados ---
        "pct_5_estrellas": dist.get("5"),
        "pct_4_estrellas": dist.get("4"),
        "pct_3_estrellas": dist.get("3"),
        "pct_2_estrellas": dist.get("2"),
        "pct_1_estrella": dist.get("1"),
        "percentil_calidad": rv.get("qualityScorePercentile"),
        "review_tags": tags or None,
        "es_favorito_huespedes": rv.get("isGuestFavorite"),
        "es_anuncio_nuevo": rv.get("isNewListing"),
        "reviews_total": rv.get("overallCount"),
        "rating_reviews": rv.get("overallRating"),
        "scraped_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    amen = []
    for g in (B.get("AMENITIES_DEFAULT") or {}).get("seeAllAmenitiesGroups") or []:
        for a in g.get("amenities") or []:
            amen.append({
                "listing_id": listing_id,
                "grupo": g.get("title"),
                "amenity": a.get("title"),
                "subtitulo": a.get("subtitle"),
                "disponible": a.get("available"),
                "icono": a.get("icon"),
            })
    return rec, amen


def main():
    ap = argparse.ArgumentParser()
    hoy = date.today()
    ap.add_argument("--checkin", default=str(hoy + timedelta(days=45)))
    ap.add_argument("--checkout", default=str(hoy + timedelta(days=50)))
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sufijo", default="",
                    help="sufijo de los archivos de la serie (ver scrape_search)")
    ap.add_argument("--sin-crudo", action="store_true",
                    help="no guardar la respuesta cruda (ahorra ~36 KB por anuncio, a cambio de tener que re-scrapear si cambia el parser)")
    ap.add_argument("--reusar-fichas", default="",
                    help="ruta de un pdp_raw.jsonl ya bajado: los anuncios que "
                         "estén ahí no se vuelven a pedir. La ficha no depende "
                         "de la ventana de fechas, así que se puede reusar")
    args = ap.parse_args()

    global SEARCH_RAW, PDP_RAW, AMEN_RAW, FULL_RAW
    if args.sufijo:
        SEARCH_RAW = OUT / f"search_raw{args.sufijo}.jsonl"
        PDP_RAW = OUT / f"pdp_raw{args.sufijo}.jsonl"
        AMEN_RAW = OUT / f"amenities_raw{args.sufijo}.jsonl"
        FULL_RAW = OUT / f"pdp_full{args.sufijo}.jsonl.gz"
        print(f"Serie aparte: {SEARCH_RAW.name} -> {PDP_RAW.name}")

    if not SEARCH_RAW.exists():
        print(f"Falta {SEARCH_RAW.name}. Corré primero scrape_search.py")
        return 1

    ids = sorted(jsonl_ids(SEARCH_RAW))
    hechos = jsonl_ids(PDP_RAW)
    if args.reusar_fichas:
        otra = Path(args.reusar_fichas)
        ya = jsonl_ids(otra)
        print(f"Reuso {len(ya)} fichas de {otra.name} (la ficha no depende de "
              f"la ventana de fechas)")
        hechos = hechos | ya
    pend = [i for i in ids if i not in hechos]
    if args.limit:
        pend = pend[: args.limit]
    print(f"{len(ids)} anuncios en el censo, {len(hechos)} ya con ficha, "
          f"{len(pend)} por procesar en esta corrida")

    session = new_session()
    fallos = 0
    for n, lid in enumerate(pend, 1):
        j, err = fetch_pdp(session, lid, args.checkin, args.checkout, args.adults)
        if err or not j:
            fallos += 1
            print(f"[{n}/{len(pend)}] {lid} ERROR: {str(err)[:120]}")
            if fallos >= 15:
                print("Demasiados errores seguidos. Corto para no insistir contra un bloqueo.")
                break
            polite_sleep(4, 2)
            continue
        fallos = 0
        # el crudo PRIMERO: si el parser falla o mañana queremos un campo que
        # hoy no leemos, el dato ya está en disco y no hay que volver a pedirlo
        if not args.sin_crudo:
            jsonl_gz_append(FULL_RAW, {
                "listing_id": lid, "checkin": args.checkin,
                "checkout": args.checkout, "adults": args.adults,
                "scraped_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "resp": j,
            })
        rec, amen = parse(lid, j)
        jsonl_append(PDP_RAW, rec)
        for a in amen:
            jsonl_append(AMEN_RAW, a)
        if n % 10 == 0 or n == 1:
            print(f"[{n}/{len(pend)}] {lid} ok — {rec.get('tipo_propiedad')}, "
                  f"{len(amen)} amenities")
        polite_sleep()

    print(f"\nListo. Fichas en {PDP_RAW.name}, amenities en {AMEN_RAW.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
