# Keskusteluforum (TSOHA K2024)


## Toiminnallisuus

**Käyttäjä**
* [x] Näkee sovelluksen etusivulla 
  * [x] Listan alueista
  * [x] Jokaisen alueen ketjujen ja viestien määrän, ja
  * [x] Viimeksi lähetetyn viestin ajankohdan
* [x] Voi 
  * [x] Rekisteröityä
  * [x] Kirjautua sisään
  * [x] Kirjautua ulos
  * [x] Luoda ketjun otsikolla ja aloitusviestillä
  * [x] Kirjoittaa viestin julkisiin ketjuihin
  * [x] Poistaa luomansa ketjun tai viestin
  * [x] Muokata otsikkoa ja viestiä
  * [x] Peukuttaa viestejä ylös tai alas
  * [x] Etsiä kaikki aiheet, joissa esiintyy haettu annettu sana

**Ylläpitäjä** 
  * [x] Voi lisätä ja poistaa keskustelualueita
  * [x] Voi luoda yksityisen alueen valituille jäsenille


## Asennus

### 1. Kloonaa repositorio

    $ sudo apt install git -y
    $ git clone https://github.com/MarkusOttela/keskusteluforum.git

### 2. Luo virtuaaliympäristö

    $ cd keskusteluforum/
    $ sudo apt install python3-pip python3-virtualenv -y
    $ python3 -m virtualenv venv

### 3. Asenna riippuvuudet

    $ source venv/bin/activate
    $ python3 -m pip install -r -requirements.txt

### 4. Luo .env tiedostoon ympäristömuuttujat

    DATABASE_URL=postgresql://<käyttäjä>:<salasana>@localhost:5432/postgres
    SECRET_KEY=<salainen avain>
    ADMIN_PASSWORD=<järjestelmänvalvojan salasana>

Salaisuuden voi luoda esim komennolla

    $ python3 -c "import os; print(os.getrandom(32, flags=0).hex())"

### 5. Käynnistä ohjelma

    (venv) $ python3 app.py
