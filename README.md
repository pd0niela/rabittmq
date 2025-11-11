# Descriere proiect RabbitMQ

Acest proiect reprezintă o demonstrație practică a modului în care funcționează RabbitMQ într-o aplicație distribuită, utilizând Python și Flask.  
Codul pornește un server web Flask care oferă o interfață grafică de joc multiplayer, iar comunicarea dintre jucători și server se realizează prin cozi RabbitMQ.

Proiectul ilustrează conceptele de:
- trimitere de mesaje între servicii (producători / consumatori)
- lucru cu mai multe cozi independente
- procesare paralelă a mesajelor prin thread-uri separate

## Mod de rulare

1. Pornirea aplicației Python:
python joc.py

3. Deschiderea jocului în browser:  
[http://localhost:5000](http://localhost:5000)

4. Accesarea panoului RabbitMQ:  
[http://localhost:15672](http://localhost:15672)  
guest:guest

## Funcționalitate

Flask oferă interfața web a jocului (pagina accesibilă în browser).  
RabbitMQ gestionează comunicarea prin cinci cozi:

- game_statistics – pentru statistici și scoruri  
- game_state – pentru starea jocului  
- game_moves – pentru mișcările jucătorilor  
- game_chat – pentru mesajele de chat  
- game_actions – pentru acțiuni generale (intrare în joc, reset, etc.)

Fiecare coadă RabbitMQ are un thread separat care ascultă și procesează mesajele.  
Când un jucător efectuează o acțiune (ex. se mișcă, plasează o bombă, trimite un mesaj), serverul trimite un mesaj în coada corespunzătoare, iar consumatorul respectiv actualizează starea jocului, vizibilă pentru toți jucătorii.

## Rezumat

- În browser: joc 2D interactiv (grilă 15×15) cu emoji pentru jucători, bombe, iteme și scoruri.  
- În consola RabbitMQ: vizualizare în timp real a mesajelor care circulă între cozi.  
- În terminalul Python: afișarea logurilor RabbitMQ (ex: Mesaj trimis, [MOVES] ...).
