from utils import scrape_symptom_detail, setup_logging
import json
import os
import time

def scrape_all_dishwasher_symptoms():
    """Scrape detailed information for all dishwasher symptoms"""
    logger = setup_logging()
    
    # Load the repair guides to get all symptom URLs
    with open('data/dishwasher_repair_guides.json', 'r', encoding='utf-8') as f:
        repair_guides = json.load(f)
    
    symptoms = repair_guides.get('common_symptoms', [])
    
    print(f"🔧 Scraping All Dishwasher Symptoms")
    print("=" * 60)
    print(f"📋 Found {len(symptoms)} symptoms to process")
    
    # Create symptoms directory
    os.makedirs('data/symptoms', exist_ok=True)
    
    results = []
    failed_symptoms = []
    
    for i, symptom in enumerate(symptoms, 1):
        symptom_title = symptom.get('title', '')
        symptom_url = symptom.get('url', '')
        percentage = symptom.get('reported_by_percentage', 0)
        
        print(f"\n🎯 Processing {i}/{len(symptoms)}: {symptom_title} ({percentage}%)")
        print(f"🌐 URL: {symptom_url}")
        
        try:
            # Skip if we already have this one (Noisy)
            filename = f"dishwasher_{symptom_title.lower().replace(' ', '_').replace('/', '_')}_detail.json"
            output_file = f'data/symptoms/{filename}'
            
            if os.path.exists(output_file):
                print(f"⏭️  Skipping {symptom_title} - already exists")
                # Load existing data for results
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                results.append({
                    'symptom': symptom_title,
                    'status': 'already_exists',
                    'file': output_file,
                    'sections_count': len(existing_data.get('repair_sections', [])),
                    'stats': existing_data.get('repair_stats', {})
                })
                continue
            
            # Scrape detailed symptom data
            print(f"🔄 Scraping detailed data...")
            symptom_data = scrape_symptom_detail(symptom_url, symptom_title, headless=True)
            
            if symptom_data and symptom_data.get('repair_sections'):
                # Save to JSON file
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(symptom_data, f, indent=2, ensure_ascii=False)
                
                file_size = os.path.getsize(output_file)
                sections_count = len(symptom_data.get('repair_sections', []))
                repair_stats = symptom_data.get('repair_stats', {})
                
                print(f"✅ SUCCESS! Saved to {output_file}")
                print(f"📊 File size: {file_size:,} bytes")
                print(f"🔧 Repair sections: {sections_count}")
                print(f"📈 Stats: {repair_stats}")
                
                results.append({
                    'symptom': symptom_title,
                    'status': 'success',
                    'file': output_file,
                    'file_size': file_size,
                    'sections_count': sections_count,
                    'stats': repair_stats
                })
            else:
                print(f"❌ FAILED - No data extracted for {symptom_title}")
                failed_symptoms.append({
                    'symptom': symptom_title,
                    'url': symptom_url,
                    'reason': 'No repair sections found'
                })
        
        except Exception as e:
            logger.error(f"Error scraping {symptom_title}: {e}")
            print(f"❌ ERROR: {e}")
            failed_symptoms.append({
                'symptom': symptom_title,
                'url': symptom_url,
                'reason': str(e)
            })
        
        # Add delay between requests to be respectful
        if i < len(symptoms):
            print(f"⏳ Waiting 5 seconds before next symptom...")
            time.sleep(5)
    
    # Generate summary report
    print(f"\n" + "="*60)
    print(f"📊 FINAL SUMMARY")
    print(f"="*60)
    
    successful = [r for r in results if r['status'] == 'success']
    existing = [r for r in results if r['status'] == 'already_exists']
    
    print(f"✅ Successful: {len(successful)}")
    print(f"⏭️  Already existed: {len(existing)}")
    print(f"❌ Failed: {len(failed_symptoms)}")
    print(f"📁 Total files: {len(successful) + len(existing)}")
    
    if successful:
        print(f"\n🎉 NEWLY SCRAPED SYMPTOMS:")
        for result in successful:
            stats = result['stats']
            difficulty = stats.get('difficulty', 'Unknown')
            stories = stats.get('repair_stories_count', 0)
            videos = stats.get('step_by_step_videos_count', 0)
            
            print(f"   ✅ {result['symptom']}")
            print(f"      📋 {result['sections_count']} sections | {difficulty} | {stories} stories | {videos} videos")
            print(f"      📄 {result['file_size']:,} bytes")
    
    if existing:
        print(f"\n📂 EXISTING SYMPTOMS:")
        for result in existing:
            print(f"   📁 {result['symptom']} - {result['sections_count']} sections")
    
    if failed_symptoms:
        print(f"\n❌ FAILED SYMPTOMS:")
        for failure in failed_symptoms:
            print(f"   ❌ {failure['symptom']}: {failure['reason']}")
    
    # Save summary report
    summary = {
        'total_symptoms': len(symptoms),
        'successful_scrapes': len(successful),
        'existing_files': len(existing),
        'failed_scrapes': len(failed_symptoms),
        'results': results,
        'failures': failed_symptoms,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open('data/symptoms/scraping_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n📋 Detailed summary saved to: data/symptoms/scraping_summary.json")
    
    return results, failed_symptoms

if __name__ == "__main__":
    scrape_all_dishwasher_symptoms()
