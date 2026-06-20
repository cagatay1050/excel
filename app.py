import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO

st.set_page_config(page_title="Ders Bilgi Güncelleyici", layout="centered", page_icon="📚")

st.title("📚 PDF'ten Ders Bilgi Otomatik Doldurucu")
st.markdown("""
Bu araç, **Excel dosyanızdaki** ders kodlarını okur ve yüklediğiniz **Bologna PDF** dosyasının içinde arayarak eksik bilgileri (AKTS, Saat, Dersin Amacı ve İçeriği) saniyeler içinde doldurur. İnternet engellerine takılmaz!
""")

col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("1. Excel/CSV Dosyanız", type=['csv', 'xlsx'])

with col2:
    pdf_file = st.file_uploader("2. Ders PDF Dosyanız", type=['pdf'])

if excel_file and pdf_file:
    try:
        # 1. Excel/CSV Dosyasını Oku
        if excel_file.name.endswith('.csv'):
            df = pd.read_csv(excel_file, skiprows=6)
        else:
            df = pd.read_excel(excel_file, skiprows=6)
            
        # 2. PDF Dosyasını Oku ve Metne Çevir
        with st.spinner("PDF dosyası okunuyor, lütfen bekleyin..."):
            reader = PyPDF2.PdfReader(pdf_file)
            pdf_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_text += extracted + "\n"
                    
        st.success("Her iki dosya da başarıyla okundu!")
        
        if 'İşlem Durumu' not in df.columns:
            df['İşlem Durumu'] = "İşlem Görmedi"
            
        if st.button("🚀 PDF'ten Verileri Çek ve Güncelle"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            toplam_ders = len(df)
            
            for index, row in df.iterrows():
                ders_kodu = str(row['Dersin Kodu']).strip()
                
                if pd.isna(row['Dersin Kodu']) or ders_kodu == "nan":
                    progress_bar.progress((index + 1) / toplam_ders)
                    continue
                
                status_text.text(f"PDF içinde aranıyor: {ders_kodu}...")
                
                # --- PDF İÇİN AKILLI ARAMA MANTIĞI ---
                # Harf ve rakamları ayırarak daha esnek arama yapalım
                harfler = "".join([c for c in ders_kodu if not c.isdigit()]).strip()
                rakamlar = "".join([c for c in ders_kodu if c.isdigit()]).strip()
                
                # Bazen O harfi yerine 0 yazılmış olabilir diye esneklik payı
                harfler_sifirsiz = harfler.replace("O", "(O|0)")
                pattern = re.compile(rf"{harfler_sifirsiz}\s*{rakamlar}", re.IGNORECASE)
                
                match = pattern.search(pdf_text)
                
                veri_bulundu_mu = False
                akts_saat_bulundu = False
                
                if match:
                    # 1. Dersin Amacı ve İçeriğini Bulma
                    start_idx = match.start()
                    # İlgili dersten sonraki 3000 karakterlik bloğu al
                    block = pdf_text[start_idx:start_idx+3000] 
                    
                    # Türkçe karakterlere ve olası boşluklara duyarlı Regex araması
                    amac_match = re.search(r'Dersin\s*Amac[ıi]\s*:\s*(.*?)(?=Dersin\s*İçerik(?:leri)?\s*:|$)', block, re.DOTALL | re.IGNORECASE)
                    icerik_match = re.search(r'Dersin\s*İçerik(?:leri)?\s*:\s*(.*?)(?=Haftalık|Öğrenme|Kaynaklar|Değerlendirme|Koordinatör|$)', block, re.DOTALL | re.IGNORECASE)
                    
                    amac = amac_match.group(1).strip() if amac_match else ""
                    icerik = icerik_match.group(1).strip() if icerik_match else ""
                    
                    # Satır atlamalarını tek boşluğa indirge
                    amac = re.sub(r'\s+', ' ', amac)
                    icerik = re.sub(r'\s+', ' ', icerik)
                    
                    if amac or icerik:
                        df.at[index, 'Dersin Amacı ve İçeriği'] = f"{amac} {icerik}".strip()
                        veri_bulundu_mu = True

                    # 2. AKTS ve Ders Saati Bulma
                    for line in pdf_text.split('\n'):
                        if pattern.search(line):
                            # Satırdaki tüm bağımsız rakamları bul
                            nums = re.findall(r'\b\d+\b', line)
                            # Genelde Kredi formatı "T U K AKTS" olduğu için
                            if len(nums) >= 3:
                                df.at[index, 'AKTS'] = nums[-1] 
                                df.at[index, 'Haftalık Ders Saati'] = nums[-3]
                                akts_saat_bulundu = True
                                break
                                
                    # Durumu Raporla
                    if veri_bulundu_mu and akts_saat_bulundu:
                        df.at[index, 'İşlem Durumu'] = "BAŞARILI: PDF'ten tüm veriler çekildi."
                    elif veri_bulundu_mu or akts_saat_bulundu:
                        df.at[index, 'İşlem Durumu'] = "KISMİ: Sadece bazı veriler bulundu."
                    else:
                        df.at[index, 'İşlem Durumu'] = "BULUNAMADI: PDF içinde dersin adı bulundu ama tablo/amaç formatı okunamadı."
                        
                else:
                    df.at[index, 'İşlem Durumu'] = "EKSİK DERS: Bu ders kodu PDF dosyasında hiç geçmiyor."
                    
                progress_bar.progress((index + 1) / toplam_ders)

            status_text.success("İşlem ışık hızında tamamlandı! Dosyayı indirebilirsiniz.")
            
            # Güncellenmiş Excel'i belleğe hazırla ve indirmeye sun
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Güncel Dersler')
            output.seek(0)
            
            st.download_button(
                label="📥 Güncellenmiş Excel Dosyasını İndir",
                data=output,
                file_name='Doldurulmus_Dersler_PDF.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

    except Exception as e:
        st.error(f"Dosya işlenirken bir hata oluştu: {e}")
