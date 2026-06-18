import math


# Obliczanie odległości euklidesowej w przestrzeni dwuwymiarowej pomiędzy dwoma punktami
def calculate_distance_2d(p1, p2):
    if not p1 or not p2:
        return 0.0
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


# Obliczanie wewnętrznego kąta (w stopniach) pomiędzy trzema punktami (a-b-c), gdzie b jest wierzchołkiem
def calculate_angle_2d(a, b, c):
    if not a or not b or not c:
        return 0.0

    # Wyznaczanie wektorów BA i BC
    ba_x = a.x - b.x
    ba_y = a.y - b.y
    bc_x = c.x - b.x
    bc_y = c.y - b.y

    # Obliczanie iloczynu skalarnego oraz długości wektorów
    dot_product = ba_x * bc_x + ba_y * bc_y
    mag_ba = math.sqrt(ba_x ** 2 + ba_y ** 2)
    mag_bc = math.sqrt(bc_x ** 2 + bc_y ** 2)

    if mag_ba == 0 or mag_bc == 0:
        return 0.0

    # Wyznaczenie cosinusa kąta i przycięcie go do zakresu [-1.0, 1.0], aby uniknąć błędów dziedziny dla math.acos
    cos_angle = dot_product / (mag_ba * mag_bc)
    cos_angle = max(-1.0, min(1.0, cos_angle))

    # Konwersja radianów na stopnie
    angle_rad = math.acos(cos_angle)
    return math.degrees(angle_rad)


# Estymacja wysokości czoła na bazie punktów oczu i uszu o najwyższej pewności detekcji
def get_forehead_y(eyes_and_ears):
    # Odfiltrowanie punktów, których widoczność (confidence) określona przez model jest zbyt niska
    valid_y = [p.y for p in eyes_and_ears if p and p.visibility > 0.5]
    if not valid_y:
        return 0.0
    # Bierzemy sam szczyt linii oczu/uszu z minimalnym offsetem
    # Uwaga: W koordynatach obrazu oś Y rośnie w dół, więc min(y) oznacza punkt położony najwyżej na ekranie
    return min(valid_y) - 0.015