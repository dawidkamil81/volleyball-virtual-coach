import pyttsx3
import speech_recognition as sr
import sys
from translate import Translator
import pyaudio

def check_hardware():
    is_hardware_ok = True
    working_microphones = sr.Microphone.list_working_microphones()
    if not working_microphones:
        print("Brak działających mikrofonów")
        is_hardware_ok = False
    
    p = pyaudio.PyAudio()    
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
        stream.close()
    except Exception:
        print("Brak działających głośników")          
        is_hardware_ok = False
    finally:
        p.terminate()

    return is_hardware_ok

def is_end_command(text):
    end_commands = ["koniec", "stop", "zakończ", "end", "stop", "finish", "bywaj", "goodbye"]
    return text in end_commands
    

def speak(text, lang_code="pl"):
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        for voice in voices:
            if lang_code == "pl" and ("polish" in voice.name.lower() or "polski" in voice.name.lower()):
                engine.setProperty('voice', voice.id)
                break
            elif lang_code == "en" and ("english" in voice.name.lower() or "angielski" in voice.name.lower() or "zira" in voice.name.lower() or "david" in voice.name.lower()):
                engine.setProperty('voice', voice.id)
                break
                
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"błąd podczas odczytywania mowy: {e}")

def choose_language(speech_recognizer):
    while True: 
        print("Wybierz język polski, czy angielski?")
        speak("Wybierz język polski, czy angielski?", "pl")
        
        try:
            with sr.Microphone() as source:
                speech_recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Mów teraz...")
                audio = speech_recognizer.listen(source, timeout=5, phrase_time_limit=5)
    
            user_text = speech_recognizer.recognize_google(audio, language="pl-PL").lower().strip()
            print(f"słowo uzytkownika: {user_text}")

            if is_end_command(user_text):
                print("Koniec programu.")
                sys.exit()

            if "polski" in user_text or "polish" in user_text:
                print("Wybrano język polski.")
                speak("Wybrano język polski.", "pl")
                return "pl", "en", "pl-PL"
        
            elif "angielski" in user_text or "english" in user_text:
                print("Wybrano język angielski.")
                speak("Wybrano język angielski.", "pl")
                return "en", "pl", "en-US"
            else:
                speak("Nie rozpoznano języka. Powiedz polski lub angielski.", "pl")

        except sr.UnknownValueError:
            speak("Błąd rozpoznawania mowy, spróbuj ponownie.", "pl")
        except sr.WaitTimeoutError:
            speak("Przekroczono czas oczekiwania, spróbuj ponownie.", "pl")

def translate_text(speech_recognizer, from_lang, to_lang, google_lang_code):
    translator = Translator(from_lang=from_lang, to_lang=to_lang)
    speech_recognizer.pause_threshold = 1.2 

    while True:
        print("Powiedz tekst do przetłumaczenia.")
        speak("Powiedz tekst do przetłumaczenia.", "pl")

        try:
            with sr.Microphone() as source:
                speech_recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = speech_recognizer.listen(source, timeout=8, phrase_time_limit=15)
            
            user_text = speech_recognizer.recognize_google(audio, language=google_lang_code).strip()
            print(f"tekst uzytkownika = {user_text}")
            speak(user_text, from_lang)

            translated_text = translator.translate(user_text)

            print(f"Tłumaczenie: {translated_text}")
            speak(translated_text, to_lang)

            print("Czy chcesz kontynuować czy zmienić język?")
            speak("Czy chcesz kontynuować czy zmienić język?", "pl")

            with sr.Microphone() as source:
                speech_recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_cmd = speech_recognizer.listen(source, timeout=5, phrase_time_limit=5)
            
            command = speech_recognizer.recognize_google(audio_cmd, language="pl-PL").lower().strip()

            if "zmiana" in command or "zmień" in command:
                speak("Wybrano zmianę języka.", "pl")
                return "change"
            elif is_end_command(user_text):
                print("Koniec programu.")
                sys.exit()
            else:
                pass 

        except sr.UnknownValueError:
             speak("Błąd rozpoznawania mowy, spróbuj ponownie.", "pl")
        except sr.WaitTimeoutError:
            speak("Przekroczono czas oczekiwania, spróbuj ponownie.", "pl")
       

if __name__ == "__main__":
    if not check_hardware():
        print("Nie można uruchomić programu z powodu problemów ze sprzętem.")
        sys.exit()

    speech_recognizer = sr.Recognizer()

    while True:
        from_lang, to_lang, google_lang_code = choose_language(speech_recognizer)
        status = translate_text(speech_recognizer, from_lang, to_lang, google_lang_code)