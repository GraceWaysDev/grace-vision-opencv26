"""Transparent provisional thresholds, not veterinary or identity judgments."""
POLICY_VERSION = "demo-1"
def decide(m):
    reasons = []
    if min(m["width"], m["height"]) < 480:
        reasons.append("Zu geringe Auflösung: kurze Seite unter 480 Pixel.")
    if m["sharpness"] < 35:
        reasons.append("Stark unscharf: Laplace-Varianz unter 35; keine künstliche Rettung.")
    if m["dark_fraction"] > .50 or m["overexposed_fraction"] > .25:
        reasons.append("Zu viele nahezu schwarze oder ausgebrannte Pixel; Details nicht wiederherstellbar.")
    if m["contrast"] < 12:
        reasons.append("Sehr geringer Kontrast; zuverlässige Details fehlen.")
    if reasons:
        return "TRY_NEXT_IMAGE", reasons
    if m["brightness"] < 90:
        reasons.append("Mittlere Helligkeit unter 90: vorsichtige Aufhellung vorschlagen.")
    elif m["brightness"] > 190:
        reasons.append("Mittlere Helligkeit über 190: vorsichtige Abdunklung vorschlagen.")
    if m["contrast"] < 35:
        reasons.append("Kontrast unter 35: begrenzten Kontrastausgleich vorschlagen.")
    if m["sharpness"] < 80:
        reasons.append("Leichte Unschärfe: nur maßvolles Nachschärfen vorschlagen.")
    return ("ENHANCE", reasons) if reasons else ("ACCEPT_ORIGINAL", ["Technische Demonstrationsschwellen erfüllt. Katzenmotiv und Identität müssen Menschen prüfen."])
