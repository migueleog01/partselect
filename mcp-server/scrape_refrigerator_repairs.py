from utils import scrape_partselect_repairs, scrape_symptom_detail, setup_logging
import json
import os
import time

def scrape_all_refrigerator_data():
    """Scrape comprehensive refrigerator repair data - main symptoms + detailed symptom guides"""
    logger = setup_logging()
    
    print(f"🧊 Scraping Complete Refrigerator Repair Data")
    print("=" * 60)
    
    # Step 1: Scrape main refrigerator repair page for symptoms and videos
    print(f"📋 Step 1: Scraping main refrigerator repair page...")
    
    try:
        # Scrape main refrigerator repair data with retry logic
        print(f"🔄 Attempting to scrape main refrigerator repair page...")
        repair_data = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                repair_data = scrape_partselect_repairs("Refrigerator", headless=True)
                if repair_data and repair_data.get('common_symptoms'):
                    break
                else:
                    print(f"⚠️  Attempt {attempt + 1} failed - no data returned")
            except Exception as e:
                print(f"⚠️  Attempt {attempt + 1} failed: {str(e)[:100]}...")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        if not repair_data or not repair_data.get('common_symptoms'):
            raise Exception("Failed to scrape main refrigerator repair data after all retries")
        
        # Create refrigerator directory to match dishwasher structure
        os.makedirs('data/refrigerator', exist_ok=True)
        os.makedirs('data/refrigerator/refrigerator_symptoms', exist_ok=True)
        
        # Save main repair guides
        main_file = 'data/refrigerator/refrigerator_repair_guides.json'
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(repair_data, f, indent=2, ensure_ascii=False)
        
        main_file_size = os.path.getsize(main_file)
        symptoms = repair_data.get('common_symptoms', [])
        videos = repair_data.get('troubleshooting_videos', [])
        
        print(f"✅ Main repair data saved to: {main_file}")
        print(f"📊 File size: {main_file_size:,} bytes")
        print(f"🔧 Found {len(symptoms)} common symptoms")
        print(f"🎥 Found {len(videos)} troubleshooting videos")
        print(f"📈 Repair stats: {repair_data.get('repair_stats', {})}")
        
        # Step 2: Scrape detailed data for each symptom
        print(f"\n📋 Step 2: Scraping detailed symptom guides...")
        print(f"Processing {len(symptoms)} symptoms...")
        
        results = []
        failed_symptoms = []
        
        for i, symptom in enumerate(symptoms, 1):
            symptom_title = symptom.get('title', '')
            symptom_url = symptom.get('url', '')
            percentage = symptom.get('reported_by_percentage', 0)
            
            print(f"\n🎯 Processing {i}/{len(symptoms)}: {symptom_title} ({percentage}%)")
            print(f"🌐 URL: {symptom_url}")
            
            try:
                # Create safe filename to match dishwasher structure
                safe_title = symptom_title.lower().replace(' ', '_').replace('/', '_').replace("'", '').replace('"', '').replace('&', 'and')
                filename = f"refrigerator_{safe_title}_detail.json"
                output_file = f'data/refrigerator/refrigerator_symptoms/{filename}'
                
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
        
        # Generate final summary
        print(f"\n" + "="*60)
        print(f"📊 REFRIGERATOR SCRAPING COMPLETE!")
        print(f"="*60)
        
        successful = len(results)
        total_sections = sum(r['sections_count'] for r in results)
        total_size = sum(r['file_size'] for r in results) + main_file_size
        
        print(f"✅ Main repair guide: 1 file ({main_file_size:,} bytes)")
        print(f"✅ Detailed symptoms: {successful}/{len(symptoms)} successful")
        print(f"❌ Failed: {len(failed_symptoms)}")
        print(f"📁 Total files: {successful + 1}")
        print(f"🔧 Total repair sections: {total_sections}")
        print(f"📊 Total data size: {total_size:,} bytes")
        
        if results:
            print(f"\n🎉 SUCCESSFULLY SCRAPED SYMPTOMS:")
            for result in results:
                stats = result['stats']
                difficulty = stats.get('difficulty', 'Unknown')
                stories = stats.get('repair_stories_count', 0)
                videos = stats.get('step_by_step_videos_count', 0)
                
                print(f"   ✅ {result['symptom']}")
                print(f"      📋 {result['sections_count']} sections | {difficulty} | {stories} stories | {videos} videos")
                print(f"      📄 {result['file_size']:,} bytes")
        
        if failed_symptoms:
            print(f"\n❌ FAILED SYMPTOMS:")
            for failure in failed_symptoms:
                print(f"   ❌ {failure['symptom']}: {failure['reason']}")
        
        # Save summary report
        summary = {
            'appliance_type': 'refrigerator',
            'main_repair_guide': {
                'file': main_file,
                'size': main_file_size,
                'symptoms_count': len(symptoms),
                'videos_count': len(videos)
            },
            'detailed_symptoms': {
                'total_symptoms': len(symptoms),
                'successful_scrapes': len(results),
                'failed_scrapes': len(failed_symptoms),
                'total_sections': total_sections,
                'results': results,
                'failures': failed_symptoms
            },
            'totals': {
                'files_created': successful + 1,
                'total_data_size': total_size
            },
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('data/refrigerator/refrigerator_symptoms/scraping_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 Detailed summary saved to: data/refrigerator/refrigerator_symptoms/scraping_summary.json")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in refrigerator scraping: {e}")
        print(f"❌ CRITICAL ERROR: {e}")
        return None

if __name__ == "__main__":
    scrape_all_refrigerator_data()
