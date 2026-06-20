import streamlit as st
import pandas as pd
import time
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

st.set_page_config(page_title="Ders Bilgi Güncelleyici", layout="centered", page_icon="📚")

st.title("📚 Ders Bilgi Paketi Otomatik Doldurucu")

@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('window-size=1920x1080') # Site tabloyu daraltmasın diye tam ekran
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

uploaded_file = st.file_uploader("Lütfen dosyanızı (.xlsx veya .csv) buraya yükleyin", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=6)
        else:
            df = pd.read_excel(uploaded_file, skiprows=6)
            
        st.success("Dosya başarıyla okundu!")
        
        if 'İşlem Durumu' not in df.columns:
            df['İşlem Durumu'] = "İşlem Görmedi"
        
        if st.button("🚀 Tarama İşlemini Başlat ve Güncelle"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            driver = get_driver()
            bologna_url = "https://obs.osmaniye.edu.tr/oibs/bologna/index.aspx?lang=tr&curOp=showPac&curUnit=29&curSunit=5815#"
            toplam_ders = len(df)
            
            for index, row in df.iterrows():
                ders_kodu = str(row['Dersin Kodu']).strip()
                
                if pd.isna(row['Dersin Kodu']) or ders_kodu == "nan":
                    progress_bar.progress((index + 1) / toplam_ders)
                    continue
                    
                status_text.text(f"İşleniyor: {ders_kodu} aranıyor...")
                
                try:
                    driver.get(bologna_url)
                    time.sleep(3) # Yüklenme süresini artırdık
                    
                    # --- 1. ADIM: Agresif Link Bulma ---
                    # Ders kodunu içeren herhangi bir satırdaki ilk tıklanabilir 'a' etiketini bul.
                    # Eğer tam kod yoksa, kodun ilk 4 harfi ve son 3 rakamını araya boşluk koyarak da (Örn: EMBO 103) dene.
                    kodu_bol = ders_kodu.replace(" ", "")
                    esnek_kod = f"{kodu_bol[:4]} {kodu_bol[4:]}" if len(kodu_bol) > 4 else ders_kodu
                    
                    xpath_sorgusu = f"//tr[contains(., '{ders_kodu}') or contains(., '{esnek_kod}')]//a"
                    
                    try:
                        ders_linki = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, xpath_sorgusu))
                        )
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ders_linki)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", ders_linki)
                        time.sleep(3) # İçerik sayfasının yüklenmesini bekle
                    except:
                        df.at[index, 'İşlem Durumu'] = "HATA: Ders listede hiç bulunamadı."
                        progress_bar.progress((index + 1) / toplam_ders)
                        continue
                    
                    # --- 2. ADIM: İçerik Sayfasında Verileri Arama ---
                    veri_bulundu = False
                    
                    try:
                        akts = driver.find_element(By.XPATH, "//*[contains(translate(@id, 'akts', 'AKTS'), 'AKTS')]").text
                        df.at[index, 'AKTS'] = akts
                        veri_bulundu = True
                    except:
                        pass
                        
                    try:
                        ders_amaci = driver.find_element(By.XPATH, "//*[contains(translate(@id, 'amac', 'AMAC'), 'AMAC')]").text
                        df.at[index, 'Dersin Amacı ve İçeriği'] = ders_amaci
                        veri_bulundu = True
                    except:
                        pass
                        
                    try:
                        haftalik_saat = driver.find_element(By.XPATH, "//*[contains(translate(@id, 'teorik', 'TEORIK'), 'TEORIK') or contains(translate(@id, 'saat', 'SAAT'), 'SAAT')]").text
                        df.at[index, 'Haftalık Ders Saati'] = haftalik_saat
                        veri_bulundu = True
                    except:
                        pass
                    
                    df.at[index, 'Varsa Ders Bilgi Paketi Adresi'] = driver.current_url
                    
                    if veri_bulundu:
                        df.at[index, 'İşlem Durumu'] = "BAŞARILI"
                    else:
                        df.at[index, 'İşlem Durumu'] = "KISMİ HATA: Sayfaya girildi ama veriler (HTML kimlikleri) okunamadı."
                        
                except Exception as e:
                    df.at[index, 'İşlem Durumu'] = f"SİSTEM HATASI: {str(e)[:50]}"
                
                progress_bar.progress((index + 1) / toplam_ders)

            status_text.success("Tarama tamamlandı! Dosyayı indirebilirsiniz.")
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Güncel Dersler')
            output.seek(0)
            
            st.download_button(
                label="📥 Güncellenmiş Excel Dosyasını İndir",
                data=output,
                file_name='Doldurulmus_Dersler_V2.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            
    except Exception as e:
        st.error(f"Dosya işlenirken bir hata oluştu: {e}")
