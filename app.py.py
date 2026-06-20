import streamlit as st
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

st.set_page_config(page_title="Ders Bilgi Güncelleyici", layout="centered")

st.title("📚 Ders Bilgi Paketi Otomatik Doldurucu")
st.write("Tabletinizden veya bilgisayarınızdan CSV dosyanızı yükleyin, eksik veriler OBS üzerinden otomatik dolsun.")

# Selenium için arka plan (headless) ayarları
@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Streamlit Cloud'da çalışabilmesi için
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Dosya Yükleme Alanı
uploaded_file = st.file_uploader("Lütfen Dersler.csv dosyanızı yükleyin", type=['csv'])

if uploaded_file is not None:
    # CSV dosyasını Pandas ile oku (başlık satırlarını atlayarak)
    df = pd.read_csv(uploaded_file, skiprows=6)
    st.success("Dosya başarıyla yüklendi!")
    st.dataframe(df.head(3)) # Önizleme göster

    if st.button("Verileri Çek ve Dosyayı Güncelle"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        driver = get_driver()
        bologna_url = "https://obs.osmaniye.edu.tr/oibs/bologna/index.aspx?lang=tr&curOp=showPac&curUnit=29&curSunit=5815#"
        
        status_text.text("Bologna Bilgi Sistemine bağlanılıyor...")
        driver.get(bologna_url)
        time.sleep(3) # Sayfanın yüklenmesini bekle
        
        toplam_ders = len(df)
        
        # Her bir ders için verileri çek
        for index, row in df.iterrows():
            ders_kodu = row['Dersin Kodu']
            
            if pd.isna(ders_kodu):
                continue
                
            status_text.text(f"İşleniyor: {ders_kodu}...")
            
            try:
                # DİKKAT: Buradaki XPATH'ler sitenin yapısına göre güncellenmelidir
                ders_linki = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, f"//td[contains(text(), '{ders_kodu}')]/following-sibling::td/a"))
                )
                driver.execute_script("arguments[0].click();", ders_linki)
                time.sleep(2)
                
                # Sitedeki HTML ID'lerini bularak verileri çekme (Örnek ID'ler)
                akts = driver.find_element(By.ID, "akts_alan_id").text
                ders_amaci = driver.find_element(By.ID, "amac_alan_id").text
                haftalik_saat = driver.find_element(By.ID, "saat_alan_id").text
                
                df.at[index, 'AKTS'] = akts
                df.at[index, 'Dersin Amacı ve İçeriği'] = ders_amaci
                df.at[index, 'Haftalık Ders Saati'] = haftalik_saat
                df.at[index, 'Varsa Ders Bilgi Paketi Adresi'] = driver.current_url
                
                driver.back() # Ana listeye dön
                time.sleep(2)
                
            except Exception as e:
                st.warning(f"{ders_kodu} için veri çekilemedi.")
            
            # İlerleme çubuğunu güncelle
            progress_bar.progress((index + 1) / toplam_ders)

        status_text.text("İşlem tamamlandı! 🎉")
        
        # Güncellenmiş dosyayı indirme butonu
        csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="Güncellenmiş Dosyayı İndir",
            data=csv,
            file_name='Guncellenmis_Dersler.csv',
            mime='text/csv',
        )