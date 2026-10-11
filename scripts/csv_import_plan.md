# CSV Import Plan for WPBA & WPA Rankings

## 🎯 **Goal**: Replace web scraping with direct CSV imports from official sources

## 📋 **Current Scraping Process**
- WPBA rankings scraped from: `https://wpba.com/rankings/`
- WPA rankings scraped from: `https://wpa-pool.com/rankings/`
- Process: HTML parsing → data extraction → cleanup → database storage
- Issues: Site changes break scrapers, rate limiting, maintenance overhead

## 🚀 **Proposed CSV Import Process**

### **Step 1: Contact Organizations**
**WPBA Contact:**
- Website: https://wpba.com/
- Contact: user4@example.com or user5@example.com
- Request: CSV export of current women's professional rankings

**WPA Contact:**
- Website: https://wpa-pool.com/
- Contact: user6@example.com
- Request: CSV exports for Men's, Women's, and Heyball rankings

### **Step 2: CSV Format Requirements**
Expected CSV columns:
```csv
Player Name,Rank,Points,Country,License Number,Fargo Rating,Recent Tournaments
Kristina Tkach,1,132750,AIN,EPBF - 046,747,10
Pia Filler,2,128250,GER,EPBF - 061,720,10
```

### **Step 3: Implementation Plan**

#### **A. Create CSV Import Endpoints**
```python
# api/routes/csv_import.py
@router.post("/import/wpba")
async def import_wpba_csv(file: UploadFile, _user: dict = Depends(require_admin))

@router.post("/import/wpa")
async def import_wpa_csv(file: UploadFile, _user: dict = Depends(require_admin))
```

#### **B. CSV Processing Logic**
- Validate CSV format and required columns
- Normalize player names using existing name format memory
- Update rankings with CSV data
- Preserve existing Fargo ratings and enrichment data
- Log import statistics and any data conflicts

#### **C. Admin Interface**
- File upload interface in admin panel
- Import history and status tracking
- Validation reports for uploaded CSVs
- Automated scheduling options

### **Step 4: Benefits**
- ✅ **Reliability**: No dependency on website structure changes
- ✅ **Performance**: Direct data loading vs HTML parsing
- ✅ **Accuracy**: Official data straight from source
- ✅ **Maintenance**: Minimal ongoing maintenance required
- ✅ **Speed**: Much faster than scraping multiple pages

### **Step 5: Migration Strategy**
1. **Phase 1**: Implement CSV import alongside existing scraping
2. **Phase 2**: Test CSV imports with sample data
3. **Phase 3**: Contact WPBA/WPA for official CSV access
4. **Phase 4**: Switch to CSV as primary data source
5. **Phase 5**: Keep scraping as fallback for when CSV unavailable

### **Step 6: Fallback Plan**
- If CSV access not granted, implement improved scraping with:
  - Better error handling and retry logic
  - Site change detection and notifications
  - Cached fallback data
  - Multiple data source redundancy

## 📞 **Action Items**
1. **Contact WPBA** - Request CSV export capability
2. **Contact WPA** - Request CSV export capability
3. **Implement CSV import endpoints** in parallel
4. **Create admin upload interface**
5. **Test with sample CSV data**

## 🎯 **Expected Outcome**
- **Faster data updates** with official CSV files
- **More reliable rankings** with direct data access
- **Reduced maintenance** from scraping dependencies
- **Better user experience** with fresher, more accurate data