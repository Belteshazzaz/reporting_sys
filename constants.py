# psr/constants.py

PSR_TEMPLATES = {
    "PRESENTATION OF PROGRESS REPORT": {
        "code": "PSR_01",
        "slug": "progress_report",
        "requires_common_fields": True,
        "category": "core"
    },

    "DATA ON TARGETS ACHIEVED": {
        "code": "PSR_02",
        "slug": "targets_achieved",
        "requires_common_fields": False,
        "category": "targets"
    },

    "DATABASE ON CONSUMER COMPLAINTS RECEIVED": {
        "code": "PSR_03",
        "slug": "complaints_received",
        "category": "complaints"
    },

    "DATABASE FOR ONGOING CONSUMER COMPLAINTS": {
        "code": "PSR_04",
        "slug": "complaints_ongoing",
        "category": "complaints"
    },

    "DATABASE ON COMPLAINTS RESOLVED": {
        "code": "PSR_05",
        "slug": "complaints_resolved",
        "category": "complaints"
    },

    "DATABASE ON ENFORCEMENT OPERATIONS": {
        "code": "PSR_06",
        "slug": "enforcement_operations",
        "category": "enforcement"
    },

    "DATABASE ON SURVEILLANCE OPERATIONS": {
        "code": "PSR_07",
        "slug": "surveillance_operations",
        "category": "surveillance"
    },

    "DATABASE ON SURVEILLANCE TIPS": {
        "code": "PSR_08",
        "slug": "surveillance_tips",
        "category": "surveillance"
    },

    "DATABASE ON REGISTRATION AND MONITORING OF SALES PROMOTION - A": {
        "code": "PSR_09A",
        "slug": "sales_promo_a",
        "category": "sales_promotion"
    },

    "DATABASE ON REGISTRATION AND MONITORING OF SALES PROMOTION - B": {
        "code": "PSR_09B",
        "slug": "sales_promo_b",
        "category": "sales_promotion"
    },

    "INPUT TO DATA BANK: CONSUMER AWARENESS CAMPAIGNS": {
        "code": "PSR_11",
        "slug": "consumer_awareness",
        "category": "outreach"
    },

    "INPUT TO DATA BANK: RADIO AND TELEVISION PROGRAMMES": {
        "code": "PSR_12",
        "slug": "radio_tv_programmes",
        "category": "outreach"
    },

    "INPUT TO DATA BANK: WORKSHOPS": {
        "code": "PSR_13",
        "slug": "workshops",
        "category": "outreach"
    },

    "INPUT TO DATA BANK: PUBLICATIONS": {
        "code": "PSR_14",
        "slug": "publications",
        "category": "outreach"
    },

    "DATABASE ON NGOS RELEVANT TO CONSUMER PROTECTION": {
        "code": "PSR_15",
        "slug": "ngos",
        "category": "partners"
    },

    "DATABASE ON TESTS & QUALITY ASSESSMENT": {
        "code": "PSR_16",
        "slug": "quality_assessment",
        "category": "quality"
    },

    "DATABASE ON PUBLIC RELATIONS ACTIVITIES (COURTESY VISITS/PRESS CONFERENCES, WORKSHOPS, ETC)": {
        "code": "PSR_17",
        "slug": "public_relations",
        "category": "pr"
    },

    "DATABASE ON PRINT / BROADCAST MEDIA PUBLICITY PROGRAMMES": {
        "code": "PSR_18",
        "slug": "media_publicity",
        "category": "media"
    },

    "DATABASE ON CORPORATE VISITORS": {
        "code": "PSR_19",
        "slug": "corporate_visitors",
        "category": "visitors"
    },

    "LEGAL UNIT REPORT FOR DATABASE ON COURT CASES": {
        "code": "PSR_20",
        "slug": "court_cases",
        "category": "legal"
    },
}

PSR_DYNAMIC_TEMPLATES = {
    "surveillance_operations": {
        "title": "Database on Surveillance Operations",
        "fields": [
            {"key": "sector", "label": "Sector Classification / Category"},
            {"key": "objective", "label": "Objectives / Target"},
            {"key": "date_commenced", "label": "Date Commenced", "type": "date"},
            {"key": "date_completed", "label": "Date Completed", "type": "date"},
            {"key": "location", "label": "Location Covered"},
            {"key": "address", "label": "Address"},
            {"key": "achievement", "label": "Achievement"},
            {"key": "remarks", "label": "Remarks"},
        ]
    },
    
    "surveillance_tips": {
    "title": "Database on Surveillance Tips",
    "fields": [
        {"key": "sector", "label": "Sector Classification / Category"},
        {"key": "date_received", "label": "Date & Time Received", "type": "datetime-local"},
        {"key": "tip", "label": "Surveillance Tip"},
        {"key": "informant", "label": "Informant (Name & Full Address)"},
        {"key": "accused", "label": "Accused (Name & Full Address)"},
        {"key": "action_taken", "label": "Action Taken"},
        {"key": "status", "label": "Status (with Date & Time)"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
    
    "sales_promo_a": {
    "title": "Database on Registration and Monitoring of Sales Promotion - A",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "category", "label": "Category"},
        {"key": "company_name", "label": "Name of Company"},
        {"key": "promotion_description", "label": "Name & Description of Promotion"},
        {"key": "registration_date", "label": "Registration Date", "type": "date"},
        {"key": "promotion_value", "label": "Value of Promotion (₦)"},
        {"key": "assessed_fee", "label": "Assessed Fee to be Paid by Applicant"},
        {"key": "duration", "label": "Duration of Promotion"},
        {"key": "action_taken", "label": "Action Taken"},
    ]
},
    
    "sales_promo_b": {
    "title": "Database on Registration and Monitoring of Sales Promotion - B",
    "fields": [
        {"key": "sector", "label": "Sector Classification / Category"},
        {"key": "company_name", "label": "Name of Company"},
        {"key": "promotion_description", "label": "Name & Description of Sales Promotion"},
        {"key": "registration_date", "label": "Registration Date", "type": "date"},
        {"key": "monitoring_dates", "label": "Monitoring Date(s)"},
        {"key": "observations", "label": "Observations"},
        {"key": "action_taken", "label": "Action Taken"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
    
   "consumer_awareness": {
    "title": "Input to Data Bank: Consumer Awareness Campaigns",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "title_campaign", "label": "Title of Campaign"},
        {"key": "date_started", "label": "Date Started", "type": "date"},
        {"key": "objective", "label": "Objective of Campaign"},
        {"key": "locations", "label": "Location(s) Covered"},
        {"key": "target_audience", "label": "Target Audience"},
        {"key": "achievement_level", "label": "Level of Achievement (%)"},
        {"key": "date_completed", "label": "Date Completed", "type": "date"},
        {"key": "remarks", "label": "Remarks"},
    ]
}, 
   
   "radio_tv_programmes": {
    "title": "Input to Data Bank: Radio and Television Programmes",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "title_programme", "label": "Title of Programme / Media Used"},
        {"key": "date_started", "label": "Date Started", "type": "date"},
        {"key": "objective", "label": "Objective of Programme"},
        {"key": "area_covered", "label": "Area Covered"},
        {"key": "target_audience", "label": "Target Audience"},
        {"key": "achievement_level", "label": "Level of Achievement (%)"},
        {"key": "date_completed", "label": "Date Completed", "type": "date"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "workshops": {
    "title": "Input to Data Bank: Workshops",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "title_workshop", "label": "Title of Workshop"},
        {"key": "date_started", "label": "Date Started", "type": "date"},
        {"key": "objective", "label": "Objective of Workshop"},
        {"key": "venue", "label": "Venue of Workshop"},
        {"key": "target_audience", "label": "Target Audience"},
        {"key": "achievement_level", "label": "Level of Achievement (%)"},
        {"key": "date_completed", "label": "Date Completed", "type": "date"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "publications": {
    "title": "Input to Data Bank: Publications",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "publication", "label": "Publication / Copies Produced"},
        {"key": "date", "label": "Date", "type": "date"},
        {"key": "objective", "label": "Objective of Publication"},
        {"key": "languages", "label": "Languages"},
        {"key": "target_audience", "label": "Target Audience"},
        {"key": "achievement_level", "label": "Level of Achievement (%)"},
        {"key": "copies_distributed", "label": "Copies Distributed"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "ngos": {
    "title": "Database on NGOs Relevant to Consumer Protection",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "ngo_name", "label": "Name of NGO"},
        {"key": "address", "label": "Address"},
        {"key": "objectives", "label": "Objectives"},
        {"key": "relationship", "label": "Understanding/Agreement - Relationship"},
        {"key": "agreement_date", "label": "Understanding/Agreement - Date", "type": "date"},
        {"key": "implementation_status", "label": "Status of Implementation of Agreement"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "quality_assessment": {
    "title": "Database on Tests & Quality Assessment",
    "fields": [
        {"key": "sector", "label": "Sector Classification / Category"},
        {"key": "date_commenced", "label": "Date Commenced", "type": "date"},
        {"key": "description", "label": "Description of Tests / Quality Assessment"},
        {"key": "objectives", "label": "Objectives"},
        {"key": "date_completed", "label": "Date Completed", "type": "date"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "public_relations": {
    "title": "Database on Public Relations Activities",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "description", "label": "Description of Activity"},
        {"key": "period", "label": "Period Covered (Dates)"},
        {"key": "organization", "label": "Organization Visited / Venue"},
        {"key": "objectives", "label": "Objectives"},
        {"key": "achievement", "label": "Achievement"},
        {"key": "remarks", "label": "Remarks"},
        {"key": "cost", "label": "Cost (₦)"},
    ]
},
   
   "media_publicity": {
    "title": "Database on Print / Broadcast Media Publicity Programmes",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "period", "label": "Period Covered (Dates)"},
        {"key": "description", "label": "Description of Programme"},
        {"key": "objectives", "label": "Objectives"},
        {"key": "target_audience", "label": "Target Audience"},
        {"key": "media_used", "label": "Media Utilized"},
        {"key": "achievement_level", "label": "Level of Achievement (% of Target)"},
        {"key": "cost", "label": "Cost (₦)"},
        {"key": "frequency", "label": "Frequency per Week"},
    ]
},
   
   "corporate_visitors": {
    "title": "Database on Corporate Visitors",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "date", "label": "Date", "type": "date"},
        {"key": "visitor", "label": "Name / Designation of Visitor"},
        {"key": "organization", "label": "Name of Organization"},
        {"key": "sector", "label": "Sector / Industry"},
        {"key": "comment", "label": "Visitor's Comment"},
        {"key": "purpose", "label": "Purpose of Visit"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
   
   "court_cases": {
    "title": "Legal Unit Report for Database on Court Cases",
    "fields": [
        {"key": "sn", "label": "S/N"},
        {"key": "date", "label": "Date", "type": "date"},
        {"key": "description", "label": "Description of Cases"},
        {"key": "plaintiff", "label": "Plaintiff"},
        {"key": "defendant", "label": "Defendant"},
        {"key": "status", "label": "Status of Case (Details)"},
        {"key": "remarks", "label": "Remarks"},
    ]
},
    
}


def get_psr_meta(slug):
    for title, data in PSR_TEMPLATES.items():
        if data["slug"] == slug:
            return {
                "title": title,
                "code": data.get("code", ""),
                "category": data.get("category", ""),
                "slug": slug
            }

    # fallback if not found
    return {
        "title": slug.replace("_", " ").title(),
        "code": "",
        "category": "",
        "slug": slug
    }
