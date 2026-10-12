import os
import re
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from src import db_session
from .utils import resource_path, short_price
from reportlab.lib.utils import simpleSplit
from PIL import Image
from .models import Reservation, Product, Customer

def generate_pdf_confirmation(order_id):
    if order_id == -1:
        return
    reservation = db_session.query(Reservation, Product, Customer)\
                .join(Product, Reservation.product_id == Product.id)\
                .join(Customer, Reservation.customer_id == Customer.id)\
                .filter(Reservation.id == order_id)\
                .first()
    document_title = 'potwierdzenie'
    title = "Potwierdzenie rezerwacji"
    directory = os.path.join(os.path.expanduser("~"), "Dokumenty")
    if not os.path.isdir(directory):
        directory = os.path.join(os.path.expanduser("~"), "Documents")
    
    directory = os.path.join(directory, "potwierdzenia_rez")
    if not os.path.isdir(directory):
        os.mkdir(directory)
    file_name = re.sub(r'[^a-zA-Z0-9]', '', reservation.Customer.name.lower())
    file_num = 1
    while os.path.exists(os.path.join(directory, file_name+str(file_num)+'.pdf')): file_num+=1
    if file_num != 1:
        file_name = file_name+str(file_num)+'.pdf'
    else:
        file_name = file_name+'.pdf'
    header = Image.open(resource_path(os.path.normpath('static/header2.jpg')))
    #print(pdfmetrics.getRegisteredFontNames())
    ARIAL_CANDIDATES = [
        ('arial.ttf', 'arialbd.ttf'),
        ('Arial.ttf', 'Arialbd.ttf'),
        ('Arial.ttf', 'Arial Bold.ttf'),
    ]

    font = 'Helvetica'
    font_bold = 'Helvetica-Bold'

    for regular_file, bold_file in ARIAL_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont('Arial', regular_file))
            pdfmetrics.registerFont(TTFont('Arial-Bold', bold_file))
            
            pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold')
            
            font = 'Arial'
            font_bold = 'Arial-Bold'
            break
        except (TTFError, FileNotFoundError, OSError):
            continue

    pdf = canvas.Canvas(os.path.join(directory, file_name))
    #pdf = canvas.Canvas(file_name)
    pdf.setTitle(document_title) 
    font_size = 11
    pdf.setFont(font, font_size)
    width = pdf._pagesize[0]
    padding = 15 * mm
    max_width = 180 * mm
    interline = 13
    binterline = interline*1.333
    pdf.drawInlineImage(header, 0, (29.7-3.75)*cm, width=11*cm, height=3.5*cm)
    contact = open(resource_path(os.path.normpath('static/seller_contact.txt')), "r", encoding="utf-8").read().strip()
    details = open(resource_path(os.path.normpath('static/seller_details.txt')), 'r', encoding="utf-8").read().strip()
    
    lines = contact.splitlines()
    lasty=804
    for  line in lines:
        pdf.drawRightString(width - padding - 5*mm, lasty, line)
        lasty-=interline
    
    pdf.line(25, (29.7-4)*cm, 555, (29.7-4)*cm) 
    lasty -= 3*interline
    pdf.drawRightString(210*mm-padding, lasty, f"Podkowa Leśna, dn. {reservation.Reservation.date.strftime('%d.%m.%Y')}r.")
    lasty -= interline
    pdf.setFont(font_bold, font_size)
    pdf.drawCentredString(290, lasty, "Zamówienie nr. " + str(reservation.Reservation.string_order_id))
    pdf.setFont(font, font_size)
    lasty -= binterline


    pdf.drawString(padding, lasty, "SPRZEDAJĄCY:")
    pdf.line(padding, lasty-3, padding+83, lasty-3)
    lasty -= binterline
    lines = details.splitlines()
    for line in lines:
        pdf.drawString(padding, lasty, line)
        lasty -= interline

    lasty -= interline

    buyer_details = ["Imię i nazwisko: "+reservation.Customer.name, "Tel: " + reservation.Customer.phone]
    if reservation.Customer.email != "" and reservation.Customer.email is not None:
        buyer_details.append("Adres e-mail: "+reservation.Customer.email)
    if reservation.Customer.company_name != "" and reservation.Customer.company_name is not None:
        buyer_details.append("Nazwa firmy: "+reservation.Customer.company_name)
    if reservation.Customer.nip != "" and reservation.Customer.nip is not None:
        buyer_details.append("NIP: "+reservation.Customer.nip)
    if reservation.Customer.pesel != "" and reservation.Customer.pesel is not None:
        buyer_details.append("PESEL: "+reservation.Customer.pesel)
    if reservation.Customer.adress != "" and reservation.Customer.adress is not None:
        buyer_details.append("Pełny adres: " + reservation.Customer.adress.replace("\n", ", ").replace("\t", ""))

    pdf.drawString(padding, lasty, "KUPUJĄCY:")
    pdf.line(padding, lasty-3, padding+62, lasty-3)
    lasty -= binterline
    
    for  line in buyer_details:
        pdf.drawString(padding, lasty, line)
        lasty -= interline

    lasty -= interline
    pdf.drawString(padding, lasty, "Kupujący zamawia następujący pojazd:")
    pdf.line(padding, lasty-3, padding+192, lasty-3)

    lasty -= binterline
    pdf.drawString(padding, lasty, "Marka i model: "+reservation.Product.brand+' '+reservation.Product.model)
    lasty -= interline
    pdf.drawString(padding, lasty, "Rok produkcji: "+str(reservation.Product.year))
    lasty -= interline
    pdf.drawString(padding, lasty, "Kolor: "+reservation.Product.colour)
    lasty -= 2*interline
    pdf.drawString(padding, lasty, "CENA POJAZDU: "+str(short_price(int(reservation.Product.price))).replace('.', ',')+'zł')
    lasty -= interline
    pdf.drawString(padding, lasty, "Słownie: "+slownie(int(reservation.Product.price), 'krótka')+' PLN')
    lasty -= 2*interline
    
    zastrzezenie = f"SPRZEDAJĄCY zastrzega prawo do zmiany ceny pojazdu w przypadku jej zmiany w oficjalnym cenniku importera marki {reservation.Product.brand} Polska."
    lines = simpleSplit(zastrzezenie, font, font_size, max_width)
    
    for line in lines:
        pdf.drawString(padding, lasty, line)
        lasty-=interline
    lasty -= interline

    if reservation.Reservation.advance in [0, reservation.Product.price]: pay_full = True
    else: pay_full = False 
    


    if reservation.Reservation.payment_method not in ["gotówka", "karta"]:
        accounts = json.load(open(resource_path("static/acc_numbers.json"), "r", encoding="utf-8"))
        acc_num = accounts[reservation.Reservation.payment_method]
        if not pay_full:
            pay = reservation.Reservation.advance
            if reservation.Reservation.form: zadzal = 'zadatku'
            else: zadzal = 'zaliczki'
        else:
            pay = reservation.Product.price
            zadzal = "pełnej kwoty wartości pojazdu"
        zaliczka = f"KUPUJĄCY zobowiązuje się do wpłaty {zadzal} w wysokości {short_price(pay)}zł (słownie: {slownie(int(pay), 'krótka')} PLN) na numer rachunku: {acc_num}."
        lines = simpleSplit(zaliczka, font, font_size, max_width)
        for line in lines:
            pdf.drawString(padding, lasty, line)
            lasty-=interline
        lasty -= interline
        zadzal = zadzal.replace("pełnej kwoty ", "")
        adit_info = f"Zamówienie zostanie przyjęte do realizacji w momencie zaksięgowania kwoty {zadzal} na rachunku SPRZEDAJĄCEGO."
        lines = simpleSplit(adit_info, font, font_size, max_width)
        for line in lines:
            pdf.drawString(padding, lasty, line)
            lasty-=interline
        lasty -= interline
    else:
        if not pay_full:
            pay = reservation.Reservation.advance
            if reservation.Reservation.form: zadzal = 'zadatek'
            else: zadzal = 'zaliczkę'
        else:
            pay = reservation.Product.price
            zadzal = "pełną kwotę wartości pojazdu"

        if reservation.Reservation.payment_method == "gotówka": how = 'gotówką'
        else: how = 'kartą/BLIK'

        zaliczka = f"KUPUJĄCY wpłacił {zadzal} w wysokości {short_price(pay)}zł (słownie: {slownie(int(pay), 'krótka')} PLN) {how}."
        lines = simpleSplit(zaliczka, font, font_size, max_width)
        for line in lines:
            pdf.drawString(padding, lasty, line)
            lasty-=interline
        lasty -= interline



    
    lines = simpleSplit(f"Przewidywany termin realizacji zamówienia: {reservation.Reservation.term}", font, font_size, max_width)
    for line in lines:
        pdf.drawString(padding, lasty, line)
        lasty-=interline
    lasty -= interline
        
    if not reservation.Reservation.delivery:
        adres = open(resource_path(os.path.normpath("static/seller_adress.txt")), "r", encoding="utf-8").read().strip()
        pickup = f"Miejsce odbioru pojazdu: {adres}."
        lines = simpleSplit(pickup, font, font_size, max_width)
        for line in lines:
            pdf.drawString(padding, lasty, line)
            lasty-=interline
        lasty -= interline
    
    if reservation.Reservation.adnotation_pub != "" and reservation.Reservation.adnotation_pub is not None:
        adnotations = f"Dodatkowe informacje: {reservation.Reservation.adnotation_pub}"
        lines = simpleSplit(adnotations, font, font_size, max_width)
        for line in lines:
            pdf.drawString(padding, lasty, line)
            lasty-=interline


    lasty -= 2 * interline

    pdf.drawString(2.5*padding, lasty, "SPRZEDAJĄCY")
    pdf.drawRightString(210*mm - 2.5*padding, lasty, "KUPUJĄCY")

    pdf.save()

    #print_file(os.path.join(directory, file_name))



def slownie(liczba:int, skala:str='długa', jeden:bool=True):
    # Zamiana liczby na slowa z polska gramatyka
    # source: www.algorytm.org
	'''
	Zamienia liczbę na zapis słowny w języku polskim.
	Obsługuje liczby w zakresie do 10^66-1 dla długiej skali oraz 10^36-1 dla krótkiej skali.
	Możliwe pominięcie słowa "jeden" przy potęgach tysiąca.
	'''
	if (skala == 'długa' and abs(liczba) >= 10**66) or (skala == 'krótka' and abs(liczba) >= 10**36):
		raise ValueError('Zbyt duża liczba.')
	
	
	jedności   = ('', 'jeden',      'dwa',         'trzy',        'cztery',       'pięć',         'sześć',         'siedem',         'osiem',         'dziewięć')
	naście     = ('', 'jedenaście', 'dwanaście',   'trzynaście',  'czternaście',  'piętnaście',   'szesnaście',    'siedemnaście',   'osiemnaście',   'dziewiętnaście')
	dziesiątki = ('', 'dziesięć',   'dwadzieścia', 'trzydzieści', 'czterdzieści', 'pięćdziesiąt', 'sześćdziesiąt', 'siedemdziesiąt', 'osiemdziesiąt', 'dziewięćdziesiąt')
	setki      = ('', 'sto',        'dwieście',    'trzysta',     'czterysta',    'pięćset',      'sześćset',      'siedemset',      'osiemset',      'dziewięćset')
	

	
	grupy = [ #kolejne potęgi tysiąca, z formami gramatycznymi
		('', '', ''),
		('tysiąc', 'tysiące', 'tysięcy'),
	]
	
	przedrostki = ('mi',  'bi', 'try', 'kwadry', 'kwinty', 'seksty', 'septy', 'okty', 'nony', 'decy')
	for p in przedrostki:
		grupy.append((f'{p}lion',  f'{p}liony',  f'{p}lionów'))
		if skala == 'długa':
			grupy.append((f'{p}liard', f'{p}liardy', f'{p}liardów'))
	
	if liczba == 0:
		return 'zero'
	
	słowa = []
	znak = ''
	if liczba < 0:
		znak = 'minus'
		liczba = -liczba
	
	g = 0
	while liczba != 0:
		#Liczba jest dzielona na kolejne potęgi tysiąca, od największej.
		s = liczba % 1_000 // 100
		d = liczba % 100 // 10
		j = liczba % 10
		liczba //= 1_000
		
		if s == d == j == 0: #brak elementów do nazwania
			g += 1
			continue
		
		if d == 1 and j > 0: #łączymy dziesiątki i jedności w -naście
			n = j
			d = j = 0
		else:
			n = 0
		
		#wybór formy gramatycznej
		if j == 1 and s + d + n == 0:
			forma = 0
		elif 2 <= j <= 4:
			forma = 1
		else:
			forma = 2
		
		słowa = [setki[s], dziesiątki[d], naście[n], jedności[j] if jeden or g == 0 else '', grupy[g][forma]] + słowa
		g += 1
	
	słowa.insert(0, znak)
	return ' '.join(s for s in słowa if s)


generate_pdf_confirmation(427)