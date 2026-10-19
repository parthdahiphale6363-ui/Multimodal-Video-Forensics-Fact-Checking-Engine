"""
generate_benchmark_100.py — Script to generate and save the 100-case labeled evaluation benchmark.
Covers 9 diverse categories with ground truth verdicts, difficulty levels, and labeled evidence passages.
"""

import json
import os

cases = [
    # ── Category 1: Health & Medicine (12 cases) ──
    {
        "id": "eval-001",
        "claim": "Sucking venom from a snakebite wound with your mouth is recommended first aid.",
        "category": "health_medicine",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "CDC Snakebite First Aid Guidelines", "url": "https://www.cdc.gov/niosh/topics/snakes/firstaid.html", "snippet": "Do not try to suck out venom. Cutting the wound or attempting to suck out venom damages tissue and introduces infection, offering no clinical benefit.", "expected_stance": "contradicts", "domain": "cdc.gov"},
            {"title": "Red Cross First Aid Guide", "url": "https://www.redcross.org/take-a-class/first-aid/snakebite", "snippet": "Never cut the bite wound or attempt to suck out the venom. Keep the person calm and still, and seek emergency care immediately.", "expected_stance": "contradicts", "domain": "redcross.org"}
        ]
    },
    {
        "id": "eval-002",
        "claim": "Type 1 diabetes is caused by an autoimmune destruction of insulin-producing beta cells.",
        "category": "health_medicine",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "ADA Type 1 Diabetes Overview", "url": "https://diabetes.org/diabetes/type-1", "snippet": "Type 1 diabetes is an autoimmune condition where the body immune system attacks and destroys insulin-producing beta cells in the pancreas.", "expected_stance": "supports", "domain": "diabetes.org"},
            {"title": "NIH NIDDK Beta Cell Autoimmunity", "url": "https://www.niddk.nih.gov/health-information/diabetes/types/type-1", "snippet": "In type 1 diabetes, antibodies target islet beta cells, leading to absolute deficiency of insulin production.", "expected_stance": "supports", "domain": "nih.gov"}
        ]
    },
    {
        "id": "eval-003",
        "claim": "Drinking alkaline water alters overall systemic blood pH and cures cellular acidosis.",
        "category": "health_medicine",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Mayo Clinic: Alkaline Water Facts", "url": "https://www.mayoclinic.org/healthy-lifestyle/nutrition/alkaline-water", "snippet": "There is no scientific evidence that alkaline water changes systemic blood pH. The body tightly regulates blood pH between 7.35 and 7.45 via the kidneys and lungs regardless of diet.", "expected_stance": "contradicts", "domain": "mayoclinic.org"}
        ]
    },
    {
        "id": "eval-004",
        "claim": "Antibiotics are ineffective against viral infections such as influenza and the common cold.",
        "category": "health_medicine",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "WHO Antibiotic Resistance Guidance", "url": "https://www.who.int/news-room/fact-sheets/detail/antibiotic-resistance", "snippet": "Antibiotics do not kill viruses. They are only effective against bacterial infections. Using antibiotics for colds or flu contributes to antibiotic resistance.", "expected_stance": "supports", "domain": "who.int"}
        ]
    },
    {
        "id": "eval-005",
        "claim": "Vaccines cause autism in children due to MMR and thimerosal preservatives.",
        "category": "health_medicine",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Institute of Medicine Comprehensive Vaccine Review", "url": "https://www.nationalacademies.org/our-work/review-of-adverse-effects-of-vaccines", "snippet": "Dozens of large-scale international epidemiologic studies have thoroughly disproved any link between the MMR vaccine, thimerosal, and autism spectrum disorder.", "expected_stance": "contradicts", "domain": "nationalacademies.org"}
        ]
    },
    {
        "id": "eval-006",
        "claim": "Intermittent fasting produces significantly greater long-term fat loss than continuous calorie restriction in clinical trials.",
        "category": "health_medicine",
        "ground_truth_label": "misleading",
        "difficulty": "nuanced",
        "passages": [
            {"title": "NEJM Trial on Time-Restricted Eating", "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2114833", "snippet": "Among patients with obesity, a regimen of time-restricted eating was not more beneficial with regard to reduction in body weight, body fat, or metabolic risk factors than daily calorie restriction.", "expected_stance": "contradicts", "domain": "nejm.org"},
            {"title": "Cell Metabolism Short-Term Fasting", "url": "https://www.cell.com/cell-metabolism/fulltext/S1550-4131", "snippet": "Short-term early time-restricted feeding improves insulin sensitivity and blood pressure independently of weight loss.", "expected_stance": "partially_supports", "domain": "cell.com"}
        ]
    },
    {
        "id": "eval-007",
        "claim": "Eating carrots directly improves night vision and allows humans to see in pitch darkness.",
        "category": "health_medicine",
        "ground_truth_label": "misleading",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Scientific American: The Carrot Night Vision Myth", "url": "https://www.scientificamerican.com/article/fact-or-fiction-carrots-improve-your-vision/", "snippet": "Beta-carotene is necessary for normal retinal function and prevents night blindness caused by vitamin A deficiency, but extra carrots do not improve normal vision or grant seeing in darkness.", "expected_stance": "contradicts", "domain": "scientificamerican.com"}
        ]
    },
    {
        "id": "eval-008",
        "claim": "A secret clinic in Switzerland has completely cured all Alzheimer cases using quantum vibration therapy.",
        "category": "health_medicine",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-009",
        "claim": "Humans are technically capable of producing venomous or toxic salivary proteins through evolutionary gene networks.",
        "category": "health_medicine",
        "ground_truth_label": "true",
        "difficulty": "adversarial",
        "passages": [
            {"title": "PNAS Study on Oral Venom Evolution", "url": "https://www.pnas.org/doi/10.1073/pnas.2026651118", "snippet": "Research demonstrates that the genetic architecture necessary for oral venom production is preserved across amniotes, and human salivary glands retain the flexible kallikrein foundation capable of toxic evolution.", "expected_stance": "supports", "domain": "pnas.org"},
            {"title": "Pest Control Rat Poison Safety", "url": "https://www.homedepot.com/c/ab/rat-poison-precautions", "snippet": "Human handling of commercial rat poison requires masks to prevent respiratory poison exposure.", "expected_stance": "irrelevant", "domain": "homedepot.com"}
        ]
    },
    {
        "id": "eval-010",
        "claim": "High doses of vitamin C can cure cancer and eliminate tumors without conventional oncology.",
        "category": "health_medicine",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NCI High-Dose Vitamin C Overview", "url": "https://www.cancer.gov/about-cancer/treatment/cam/patient/vitamin-c-pdq", "snippet": "Clinical trials show no evidence that high-dose vitamin C monotherapy can cure cancer or replace standard oncologic treatments.", "expected_stance": "contradicts", "domain": "cancer.gov"}
        ]
    },
    {
        "id": "eval-011",
        "claim": "Blood pressure measurements taken at home are consistently 15 mmHg higher than physician office readings for all individuals.",
        "category": "health_medicine",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "AHA White Coat Hypertension Analysis", "url": "https://www.heart.org/en/health-topics/high-blood-pressure/white-coat-hypertension", "snippet": "Office blood pressure readings are frequently higher due to white-coat hypertension, refuting the claim that home readings are universally 15 mmHg higher.", "expected_stance": "contradicts", "domain": "heart.org"}
        ]
    },
    {
        "id": "eval-012",
        "claim": "A local herbal tea concoction prepared by my neighbor cured severe pancreatic adenocarcinoma in three days.",
        "category": "health_medicine",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },

    # ── Category 2: Physics & Everyday Science (11 cases) ──
    {
        "id": "eval-013",
        "claim": "Water boils at 100 degrees Celsius at standard sea level atmospheric pressure (1 atm).",
        "category": "everyday_physics",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "NIST Chemistry WebBook: Water Thermophysical Properties", "url": "https://webbook.nist.gov/chemistry/fluid/", "snippet": "Standard normal boiling point of pure water at 101.325 kPa is 99.97 to 100.00 degrees Celsius.", "expected_stance": "supports", "domain": "nist.gov"}
        ]
    },
    {
        "id": "eval-014",
        "claim": "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
        "category": "everyday_physics",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Bureau International des Poids et Mesures (BIPM)", "url": "https://www.bipm.org/en/si-base-units/metre", "snippet": "The metre is defined by taking the fixed numerical value of the speed of light in vacuum c to be 299 792 458 when expressed in m s^-1.", "expected_stance": "supports", "domain": "bipm.org"}
        ]
    },
    {
        "id": "eval-015",
        "claim": "Microwave ovens cook food from the inside out using radioactive gamma emissions.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "FDA Microwave Oven Radiation Safety", "url": "https://www.fda.gov/radiation-emitting-products/resources-you-radiation-emitting-products/microwave-ovens", "snippet": "Microwaves use non-ionizing radiofrequency radiation to excite water molecules near the surface, cooking from outside inward via thermal conduction. They emit zero gamma rays.", "expected_stance": "contradicts", "domain": "fda.gov"}
        ]
    },
    {
        "id": "eval-016",
        "claim": "Lightning never strikes the same place twice.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NOAA National Severe Storms Laboratory", "url": "https://www.nssl.noaa.gov/education/svrwx101/lightning/myths/", "snippet": "Lightning frequently strikes the same place repeatedly. Tall structures like the Empire State Building are struck dozens of times each year.", "expected_stance": "contradicts", "domain": "noaa.gov"}
        ]
    },
    {
        "id": "eval-017",
        "claim": "Sound travels faster in air than in solid steel.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Engineering Physics Handbook: Acoustic Velocity", "url": "https://www.engineeringtoolbox.com/sound-speed-solids-d_713.html", "snippet": "Sound propagates at ~343 m/s in air, but travels at over 5,000 m/s in steel due to higher density elasticity, directly disproving that air is faster.", "expected_stance": "contradicts", "domain": "engineeringtoolbox.com"}
        ]
    },
    {
        "id": "eval-018",
        "claim": "Glass is a slow-flowing liquid at room temperature as evidenced by antique cathedral windows.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Corning Museum of Glass: The Cathedral Glass Myth", "url": "https://www.cmog.org/article/does-glass-flow", "snippet": "Glass is an amorphous solid, not a liquid. Uneven thickness in medieval stained glass resulted from historic manufacturing methods, not viscous flow at room temperature.", "expected_stance": "contradicts", "domain": "cmog.org"}
        ]
    },
    {
        "id": "eval-019",
        "claim": "Quantum entanglement allows instantaneous transmission of classical data bits across interstellar distances.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Stanford Encyclopedia of Philosophy: No-Communication Theorem", "url": "https://plato.stanford.edu/entries/qm-entanglement/", "snippet": "The no-communication theorem strictly forbids the transmission of usable classical information faster than light via quantum entanglement.", "expected_stance": "contradicts", "domain": "stanford.edu"}
        ]
    },
    {
        "id": "eval-020",
        "claim": "Helium is lighter than air and causes vocal pitch to sound higher when inhaled.",
        "category": "everyday_physics",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "American Chemical Society: Chemistry of Inhaled Helium", "url": "https://www.acs.org/education/resources/highschool/chemmatters/past-issues/archive-2016-2017/helium-voice.html", "snippet": "Helium is much less dense than air. Sound waves travel faster through helium, shifting the vocal tract resonant frequencies higher.", "expected_stance": "supports", "domain": "acs.org"}
        ]
    },
    {
        "id": "eval-021",
        "claim": "A perpetual motion machine of the first kind was patented and built in Nevada in 2023.",
        "category": "everyday_physics",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "US Patent and Trademark Office Guidance on Perpetual Motion", "url": "https://www.uspto.gov/web/offices/pac/mpep/s2107.html", "snippet": "Perpetual motion machines of the first kind violate the First Law of Thermodynamics (conservation of energy) and cannot be patented or operated.", "expected_stance": "contradicts", "domain": "uspto.gov"}
        ]
    },
    {
        "id": "eval-022",
        "claim": "Diamond is composed entirely of carbon atoms arranged in a crystal lattice.",
        "category": "everyday_physics",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "USGS Minerals: Diamond Physical Characteristics", "url": "https://www.usgs.gov/centers/national-minerals-information-center/diamond-statistics-and-information", "snippet": "Diamond is an allotrope of carbon where atoms are arranged in a face-centered cubic crystal lattice structure.", "expected_stance": "supports", "domain": "usgs.gov"}
        ]
    },
    {
        "id": "eval-023",
        "claim": "A secret particle with negative mass was accidentally dropped onto the floor of my garage last Tuesday.",
        "category": "everyday_physics",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },

    # ── Category 3: Climate & Environment (11 cases) ──
    {
        "id": "eval-024",
        "claim": "Global atmospheric CO2 concentration exceeded 420 ppm as measured at Mauna Loa in 2024.",
        "category": "climate_environment",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "NOAA Global Monitoring Laboratory Carbon Cycle", "url": "https://gml.noaa.gov/ccgg/trends/", "snippet": "The Mauna Loa Observatory recorded atmospheric CO2 concentrations exceeding 426 ppm in May 2024, continuing the upward trajectory.", "expected_stance": "supports", "domain": "noaa.gov"}
        ]
    },
    {
        "id": "eval-025",
        "claim": "Volcanoes emit significantly more CO2 annually than human industrial activities.",
        "category": "climate_environment",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "USGS Volcanic Gases and Climate Change", "url": "https://www.usgs.gov/programs/volcano-hazards/volcanoes-can-affect-climate", "snippet": "Global volcanic emissions generate roughly 0.15 to 0.26 gigatons of CO2 per year, whereas human fossil fuel combustion emits over 35 gigatons per year—more than 100 times greater.", "expected_stance": "contradicts", "domain": "usgs.gov"}
        ]
    },
    {
        "id": "eval-026",
        "claim": "The Montreal Protocol successfully phased out chlorofluorocarbons (CFCs) to protect the ozone layer.",
        "category": "climate_environment",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "UNEP Montreal Protocol Assessment", "url": "https://www.unep.org/ozonaction/who-we-are/about-montreal-protocol", "snippet": "Adopted in 1987, the Montreal Protocol has phased out over 98% of controlled ozone-depleting substances worldwide.", "expected_stance": "supports", "domain": "unep.org"}
        ]
    },
    {
        "id": "eval-027",
        "claim": "Polar bear populations have gone completely extinct across all Arctic regions in 2024.",
        "category": "climate_environment",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "IUCN Polar Bear Specialist Group Status Report", "url": "https://www.polarbearsinternational.org/polar-bears-nature/population-status/", "snippet": "Polar bears are not extinct; global population is estimated between 22,000 and 31,000 across 19 sub-populations, although classified as vulnerable.", "expected_stance": "contradicts", "domain": "polarbearsinternational.org"}
        ]
    },
    {
        "id": "eval-028",
        "claim": "Solar panel manufacturing produces more carbon emissions over its lifecycle than burning coal.",
        "category": "climate_environment",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NREL Lifecycle Greenhouse Gas Emissions", "url": "https://www.nrel.gov/analysis/life-cycle-assessment.html", "snippet": "Solar photovoltaic lifecycle emissions average 40 g CO2e/kWh compared to roughly 1,000 g CO2e/kWh for coal power plants.", "expected_stance": "contradicts", "domain": "nrel.gov"}
        ]
    },
    {
        "id": "eval-029",
        "claim": "Antarctica has gained net ice mass continuously without any loss in Western glaciers over the last decade.",
        "category": "climate_environment",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "NASA GRACE Satellite Ice Mass Measurements", "url": "https://climate.nasa.gov/vital-signs/ice-sheets/", "snippet": "Satellite observations demonstrate Antarctica has been losing roughly 150 billion metric tons of ice per year, driven by rapid thinning in West Antarctica.", "expected_stance": "contradicts", "domain": "nasa.gov"}
        ]
    },
    {
        "id": "eval-030",
        "claim": "Planting trees absorbs carbon dioxide through the process of photosynthesis.",
        "category": "climate_environment",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "US Forest Service: How Trees Store Carbon", "url": "https://www.fs.usda.gov/features/how-trees-capture-and-store-carbon", "snippet": "Through photosynthesis, trees absorb atmospheric carbon dioxide, storing carbon in their trunks, roots, and soil.", "expected_stance": "supports", "domain": "fs.usda.gov"}
        ]
    },
    {
        "id": "eval-031",
        "claim": "Chemtrails from passenger airliners are sprayed intentionally to modify human DNA.",
        "category": "climate_environment",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Harvard Atmospheric Research on Contrails", "url": "https://geoengineering.environment.harvard.edu/chemtrails-conspiracy-theory", "snippet": "Contrails are water condensation trails formed by jet exhaust at high altitude. Peer-reviewed surveys show zero evidence of chemical spraying or DNA modification.", "expected_stance": "contradicts", "domain": "harvard.edu"}
        ]
    },
    {
        "id": "eval-032",
        "claim": "Ocean acidification is driven by the absorption of atmospheric CO2 forming carbonic acid.",
        "category": "climate_environment",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "NOAA Ocean Acidification Program", "url": "https://www.noaa.gov/education/resource-collections/ocean-coasts/ocean-acidification", "snippet": "When CO2 dissolves in seawater, it forms carbonic acid, reducing ocean pH and carbonate ion concentrations.", "expected_stance": "supports", "domain": "noaa.gov"}
        ]
    },
    {
        "id": "eval-033",
        "claim": "A secret tropical rainstorm will hit the Sahara desert next Friday causing ten feet of snow.",
        "category": "climate_environment",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-034",
        "claim": "Methane is a more potent greenhouse gas per molecule than carbon dioxide over a 20-year timescale.",
        "category": "climate_environment",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "IPCC Sixth Assessment Report: Methane GWP", "url": "https://www.ipcc.ch/report/ar6/wg1/", "snippet": "Methane has a global warming potential (GWP) roughly 80 times that of carbon dioxide over a 20-year timescale.", "expected_stance": "supports", "domain": "ipcc.ch"}
        ]
    },

    # ── Category 4: History & Geography (11 cases) ──
    {
        "id": "eval-035",
        "claim": "Apollo 11 landed astronauts Neil Armstrong and Buzz Aldrin on the Moon in July 1969.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Smithsonian National Air and Space Museum Apollo 11", "url": "https://airandspace.si.edu/explore/stories/apollo-11", "snippet": "On July 20, 1969, American astronauts Neil Armstrong and Buzz Aldrin became the first humans to walk on the lunar surface.", "expected_stance": "supports", "domain": "si.edu"}
        ]
    },
    {
        "id": "eval-036",
        "claim": "The Great Wall of China is visible from low Earth orbit with the unaided human eye.",
        "category": "history_geography",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "NASA: Is the Great Wall Visible from Orbit?", "url": "https://www.nasa.gov/vision/space/workinginspace/great_wall.html", "snippet": "The Great Wall of China is generally not visible to the naked human eye from low Earth orbit without magnification due to its narrow width and matching materials.", "expected_stance": "contradicts", "domain": "nasa.gov"}
        ]
    },
    {
        "id": "eval-037",
        "claim": "The Titanic sank after colliding with an iceberg in the North Atlantic in April 1912.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "British National Archives: Loss of RMS Titanic", "url": "https://www.nationalarchives.gov.uk/titanic/", "snippet": "RMS Titanic sank on April 15, 1912, after striking an iceberg south of Newfoundland during her maiden voyage.", "expected_stance": "supports", "domain": "nationalarchives.gov.uk"}
        ]
    },
    {
        "id": "eval-038",
        "claim": "Cleopatra was born closer in time to the Moon landing than to the construction of the Great Pyramid of Giza.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "nuanced",
        "passages": [
            {"title": "World History Encyclopedia: Chronology of Cleopatra", "url": "https://www.worldhistory.org/Cleopatra_VII/", "snippet": "The Great Pyramid was completed around 2560 BCE. Cleopatra VII lived around 30 BCE (~2,500 years later), whereas the 1969 Moon landing occurred ~2,000 years after her.", "expected_stance": "supports", "domain": "worldhistory.org"}
        ]
    },
    {
        "id": "eval-039",
        "claim": "Mount Everest is the highest mountain peak above sea level on Earth.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Survey of Nepal & China Joint Measurement", "url": "https://www.britannica.com/place/Mount-Everest", "snippet": "Mount Everest rises to an official elevation of 8,848.86 meters above sea level, making it Earth highest peak above sea level.", "expected_stance": "supports", "domain": "britannica.com"}
        ]
    },
    {
        "id": "eval-040",
        "claim": "The United States purchased Alaska from France in the Louisiana Purchase.",
        "category": "history_geography",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Library of Congress: Alaska Purchase Treaty", "url": "https://www.loc.gov/rr/program/bib/ourdocs/alaska.html", "snippet": "The United States purchased Alaska from the Russian Empire in 1867. The 1803 Louisiana Purchase was made from France.", "expected_stance": "contradicts", "domain": "loc.gov"}
        ]
    },
    {
        "id": "eval-041",
        "claim": "Rome was built in a single calendar day by the mythical twin Romulus.",
        "category": "history_geography",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Oxford Classical Dictionary: Early Roman Settlement", "url": "https://oxfordre.com/classics/view/10.1093/acrefore/9780199381134.001.0001/acrefore-9780199381134-e-5612", "snippet": "Archaeological evidence shows Rome grew gradually over centuries through pastoral settlements on the Palatine Hill, refuting single-day construction.", "expected_stance": "contradicts", "domain": "oxfordre.com"}
        ]
    },
    {
        "id": "eval-042",
        "claim": "Napoleon Bonaparte was unusually short and measured less than 4 feet tall.",
        "category": "history_geography",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Fondation Napoléon: Napoleon Height Records", "url": "https://www.napoleon.org/en/history-of-the-two-empires/articles/how-tall-was-napoleon/", "snippet": "Autopsy records recorded Napoleon height as 5 feet 2 inches in French units, which translates to approximately 5 feet 6.5 inches (169 cm) in modern units—average height for French men of his era.", "expected_stance": "contradicts", "domain": "napoleon.org"}
        ]
    },
    {
        "id": "eval-043",
        "claim": "The Amazon River discharges more freshwater by volume than any other river system.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Guinness World Records: Largest River by Discharge", "url": "https://www.guinnessworldrecords.com/world-records/greatest-flow-of-water-river", "snippet": "The Amazon River has an average discharge of roughly 209,000 cubic meters per second, exceeding the next seven largest rivers combined.", "expected_stance": "supports", "domain": "guinnessworldrecords.com"}
        ]
    },
    {
        "id": "eval-044",
        "claim": "In 1742, King George II had a secret pet kangaroo that he knighted as Sir Hops-a-Lot.",
        "category": "history_geography",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-045",
        "claim": "Australia was the first sovereign nation to grant all women the right to run for national parliament in 1902.",
        "category": "history_geography",
        "ground_truth_label": "true",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Australian Electoral Commission: Electoral Milestones", "url": "https://www.aec.gov.au/about_aec/publications/women/", "snippet": "The Commonwealth Franchise Act 1902 granted women the right to vote in federal elections and to stand for the federal Parliament.", "expected_stance": "supports", "domain": "aec.gov.au"}
        ]
    },

    # ── Category 5: Technology & AI (11 cases) ──
    {
        "id": "eval-046",
        "claim": "The transformer neural network architecture was introduced in the 2017 paper Attention Is All You Need.",
        "category": "technology_ai",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "arXiv: Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762", "snippet": "Vaswani et al. (2017) introduced the Transformer, a novel network architecture based entirely on attention mechanisms.", "expected_stance": "supports", "domain": "arxiv.org"}
        ]
    },
    {
        "id": "eval-047",
        "claim": "5G mobile cellular networks transmit coronavirus pathogens through radio frequency radiation.",
        "category": "technology_ai",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "FCC and WHO: 5G and Health Facts", "url": "https://www.who.int/news-room/questions-and-answers/item/radiation-5g-mobile-networks-and-health", "snippet": "Viruses cannot travel on radio waves or mobile networks. COVID-19 is a biological virus spread through respiratory droplets.", "expected_stance": "contradicts", "domain": "who.int"}
        ]
    },
    {
        "id": "eval-048",
        "claim": "Deepfake speech synthesis models can replicate vocal timbre from a few seconds of clean audio reference.",
        "category": "technology_ai",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "IEEE Transactions on Audio: Zero-Shot Voice Cloning", "url": "https://ieeexplore.ieee.org/document/voice-cloning-survey", "snippet": "Recent neural acoustic models achieve zero-shot speaker adaptation from 3 to 10 seconds of reference audio with high perceptual similarity.", "expected_stance": "supports", "domain": "ieee.org"}
        ]
    },
    {
        "id": "eval-049",
        "claim": "Quantum computers have officially broken all 2048-bit RSA encryption worldwide as of early 2024.",
        "category": "technology_ai",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NIST Post-Quantum Cryptography Program", "url": "https://csrc.nist.gov/projects/post-quantum-cryptography", "snippet": "Current noisy intermediate-scale quantum (NISQ) computers lack the millions of physical error-corrected qubits needed to factor 2048-bit RSA keys via Shor algorithm.", "expected_stance": "contradicts", "domain": "nist.gov"}
        ]
    },
    {
        "id": "eval-050",
        "claim": "Bitcoin relies on a proof-of-work consensus algorithm using SHA-256 cryptographic hashing.",
        "category": "technology_ai",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Bitcoin Whitepaper by Satoshi Nakamoto", "url": "https://bitcoin.org/bitcoin.pdf", "snippet": "The proof-of-work involves scanning for a value that when hashed, such as with SHA-256, the hash begins with a number of zero bits.", "expected_stance": "supports", "domain": "bitcoin.org"}
        ]
    },
    {
        "id": "eval-051",
        "claim": "Putting your smartphone inside a kitchen microwave for 10 seconds wirelessly recharges the lithium battery.",
        "category": "technology_ai",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Consumer Product Safety Commission Electronics Warning", "url": "https://www.cpsc.gov/safety-education/safety-guides/electronics", "snippet": "Microwaving a mobile phone sparks metal components and can trigger violent lithium-ion battery combustion, destroying the device.", "expected_stance": "contradicts", "domain": "cpsc.gov"}
        ]
    },
    {
        "id": "eval-052",
        "claim": "Large Language Models operate by predicting the probability distribution of subsequent tokens.",
        "category": "technology_ai",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "ACL Survey on Autoregressive Language Models", "url": "https://aclanthology.org/2020.cl-survey.pdf", "snippet": "Autoregressive LLMs model the joint probability of sequences by factoring them into conditional probabilities of the next token given preceding tokens.", "expected_stance": "supports", "domain": "aclanthology.org"}
        ]
    },
    {
        "id": "eval-053",
        "claim": "Tesla has launched an automated quantum financial giveaway distributing $10,000 to every viewer.",
        "category": "technology_ai",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Reuters Fact Check: Fake Elon Musk Crypto Schemes", "url": "https://www.reuters.com/fact-check/elon-musk-bitcoin-scam", "snippet": "Videos claiming Elon Musk or Tesla are distributing free crypto or money are deepfaked advance-fee fraudulent scams.", "expected_stance": "contradicts", "domain": "reuters.com"}
        ]
    },
    {
        "id": "eval-054",
        "claim": "My programmer uncle built an AI in 1984 that solved P versus NP but erased it on a floppy disk.",
        "category": "technology_ai",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-055",
        "claim": "Error Level Analysis (ELA) identifies differing JPEG compression levels across edited image regions.",
        "category": "technology_ai",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "IEEE Forensic Image Analysis Techniques", "url": "https://ieeexplore.ieee.org/document/ela-forensics", "snippet": "Error Level Analysis functions by intentional re-saving of an image at a known quality level to identify areas saved at varying compression ratios.", "expected_stance": "supports", "domain": "ieee.org"}
        ]
    },
    {
        "id": "eval-056",
        "claim": "Turning on incognito mode prevents internet service providers and network administrators from tracking visited websites.",
        "category": "technology_ai",
        "ground_truth_label": "misleading",
        "difficulty": "nuanced",
        "passages": [
            {"title": "EFF: What Private Browsing Actually Does", "url": "https://www.eff.org/deeplinks/private-browsing-myths", "snippet": "Private browsing prevents local browsing history from being stored on the client device, but ISPs, routers, and network admins still see DNS queries and IP destinations.", "expected_stance": "contradicts", "domain": "eff.org"}
        ]
    },

    # ── Category 6: Geopolitics & OSINT (11 cases) ──
    {
        "id": "eval-057",
        "claim": "The United Nations was established in 1945 following the conclusion of World War II.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "United Nations Founding History", "url": "https://www.un.org/en/about-us/history-of-the-un", "snippet": "The United Nations officially came into existence on 24 October 1945, when the UN Charter had been ratified by the majority of signatories.", "expected_stance": "supports", "domain": "un.org"}
        ]
    },
    {
        "id": "eval-058",
        "claim": "Video game combat simulator ARMA 3 clips have frequently been miscaptioned as genuine live breaking war footage.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "AP News: Video game clips falsely shared as active warfare", "url": "https://apnews.com/article/fact-check-arma-video-game", "snippet": "Footage claiming to show anti-aircraft batteries shooting down jets is computer-generated gameplay from simulator ARMA 3.", "expected_stance": "supports", "domain": "apnews.com"},
            {"title": "BBC Verify: Misinformation via video game simulators", "url": "https://www.bbc.com/news/world-arma-simulation-check", "snippet": "BBC Verify has debunked numerous viral clips derived from the game ARMA 3 circulating during conflicts.", "expected_stance": "supports", "domain": "bbc.com"}
        ]
    },
    {
        "id": "eval-059",
        "claim": "The North Atlantic Treaty Organization (NATO) was originally founded in 1949 with 12 founding members.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "NATO Founding Treaty Records", "url": "https://www.nato.int/cps/en/natohq/topics_67656.htm", "snippet": "The North Atlantic Treaty was signed in Washington on 4 April 1949 by 12 founding member states.", "expected_stance": "supports", "domain": "nato.int"}
        ]
    },
    {
        "id": "eval-060",
        "claim": "The European Union is comprised of 50 member states all using the Swiss Franc currency.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "European Union Official Member State Roster", "url": "https://european-union.europa.eu/easy-read_en", "snippet": "The European Union has 27 member states, and 20 of them use the Euro as their currency. Switzerland is not an EU member.", "expected_stance": "contradicts", "domain": "europa.eu"}
        ]
    },
    {
        "id": "eval-061",
        "claim": "Certified IFCN fact-checkers must adhere to a strict nonpartisanship and transparency code of principles.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Poynter Institute: IFCN Code of Principles", "url": "https://www.ifcncodeofprinciples.poynter.org/", "snippet": "Signatories to the IFCN Code of Principles commit to nonpartisanship, transparency of sources, methodology, and funding.", "expected_stance": "supports", "domain": "poynter.org"}
        ]
    },
    {
        "id": "eval-062",
        "claim": "A secret meeting occurred yesterday where all world leaders signed away sovereign borders to an alien federation.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-063",
        "claim": "Over 500,000 residents were evacuated from downtown Geneva due to a volcanic eruption in 2024.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Swiss Seismological Service (SED) Geological Records", "url": "https://www.seismo.ethz.ch/en/home/", "snippet": "There are no active volcanoes in Geneva or Switzerland. No volcanic evacuations have ever occurred in modern Geneva.", "expected_stance": "contradicts", "domain": "ethz.ch"}
        ]
    },
    {
        "id": "eval-064",
        "claim": "The Geneva Conventions govern the humanitarian treatment of wounded soldiers and prisoners of war.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "ICRC: The Geneva Conventions of 1949", "url": "https://www.icrc.org/en/war-and-law/treaties-customary-law/geneva-conventions", "snippet": "The Geneva Conventions and their Additional Protocols form the core of international humanitarian law, regulating conduct during armed conflict.", "expected_stance": "supports", "domain": "icrc.org"}
        ]
    },
    {
        "id": "eval-065",
        "claim": "The country of Canada has completely eliminated all national military forces and has zero defense budget.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Department of National Defence Canada Overview", "url": "https://www.canada.ca/en/department-national-defence.html", "snippet": "The Canadian Armed Forces maintain active maritime, air, and land commands with an annual defense budget exceeding 25 billion CAD.", "expected_stance": "contradicts", "domain": "canada.ca"}
        ]
    },
    {
        "id": "eval-066",
        "claim": "A diplomatic telegram from 1917 known as the Zimmermann Telegram influenced US entry into World War I.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "National Archives: The Zimmermann Telegram", "url": "https://www.archives.gov/milestone-documents/zimmermann-telegram", "snippet": "The British interception and decryption of the German telegram proposing a military alliance with Mexico galvanized American public opinion toward war.", "expected_stance": "supports", "domain": "archives.gov"}
        ]
    },
    {
        "id": "eval-067",
        "claim": "Diplomats in Paris privately whispered that next month currency will be replaced by stamps.",
        "category": "geopolitics_conflict",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },

    # ── Category 7: Pseudoscience & Conspiracies (11 cases) ──
    {
        "id": "eval-068",
        "claim": "The Earth is a flat stationary disk enclosed by an impenetrable dome of solid ice.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NASA Planetary Geophysics: Shape of Earth", "url": "https://solarsystem.nasa.gov/planets/earth/in-depth/", "snippet": "Earth is an oblate spheroid in continuous rotation and orbit around the Sun, confirmed by centuries of geodesy, lunar eclipses, and space navigation.", "expected_stance": "contradicts", "domain": "nasa.gov"}
        ]
    },
    {
        "id": "eval-069",
        "claim": "The world elite are blood-drinking shapeshifting reptilian aliens from the Alpha Draconis star system.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Skeptical Inquirer: Deconstructing Reptilian Conspiracy Theories", "url": "https://skepticalinquirer.org/2021/04/the-reptilian-conspiracy/", "snippet": "The reptilian conspiracy theory originated in science fiction and speculative writings with zero biological or empirical substantiation.", "expected_stance": "contradicts", "domain": "skepticalinquirer.org"}
        ]
    },
    {
        "id": "eval-070",
        "claim": "Astrological horoscopes accurately determine individual personality traits and forecast daily financial outcomes.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Nature Double-Blind Test of Astrology", "url": "https://www.nature.com/articles/318419a0", "snippet": "A controlled double-blind test by Carlson (1985) published in Nature disproved astrological claims, showing astrologers performed no better than chance.", "expected_stance": "contradicts", "domain": "nature.com"}
        ]
    },
    {
        "id": "eval-071",
        "claim": "Crystals have documented molecular resonance frequencies that reliably cure viral hepatitis when held against the skin.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "British Journal of Psychology: Crystal Healing Placebo Analysis", "url": "https://bpspsychub.onlinelibrary.wiley.com/doi/abs/10.1348/000712602162544", "snippet": "Clinical trials demonstrate that crystal healing effects are entirely attributable to placebo suggestion and provide no physiological therapy.", "expected_stance": "contradicts", "domain": "wiley.com"}
        ]
    },
    {
        "id": "eval-072",
        "claim": "The moon landings were filmed on a soundstage directed by Stanley Kubrick in Hollywood.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "NASA History Division: Apollo Moon Hoax Claims Addressed", "url": "https://history.nasa.gov/moonhoax.htm", "snippet": "Independent tracking by the Soviet Union, lunar laser ranging reflectors, and hundreds of kilograms of lunar samples refute moon landing hoax claims.", "expected_stance": "contradicts", "domain": "nasa.gov"}
        ]
    },
    {
        "id": "eval-073",
        "claim": "Dowsing with wooden rods reliably detects underground water aquifers through psychic magnetic attraction.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "USGS Water Science School: Water Dowsing", "url": "https://www.usgs.gov/special-topics/water-science-school/science/water-dowsing", "snippet": "Extensive controlled scientific experiments show that dowsers perform at chance levels and respond to the ideomotor effect.", "expected_stance": "contradicts", "domain": "usgs.gov"}
        ]
    },
    {
        "id": "eval-074",
        "claim": "A secret group of sorcerers in Tibet can levitate ten feet above the ground during meditation.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-075",
        "claim": "Subliminal messages flashed for 1 millisecond during movies force viewers to buy popcorn against their will.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "misleading",
        "difficulty": "nuanced",
        "passages": [
            {"title": "FTC / Psychological Science: The Subliminal Advertising Myth", "url": "https://www.psychologicalscience.org/news/were-only-human/the-myth-of-subliminal-advertising.html", "snippet": "James Vicary 1957 claim that subliminal movie flashes increased popcorn sales was admitted by Vicary himself to be a fabricated hoax.", "expected_stance": "contradicts", "domain": "psychologicalscience.org"}
        ]
    },
    {
        "id": "eval-076",
        "claim": "Bermuda Triangle disappearances occur at a statistically higher rate than any other comparable ocean shipping corridor.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "US Coast Guard and Lloyd of London Ocean Statistics", "url": "https://www.history.navy.mil/browse-by-topic/disasters-and-phenomena/bermuda-triangle.html", "snippet": "US Coast Guard and marine insurance underwriters document that ship and aircraft losses in the Bermuda Triangle are no higher than in any other heavily traveled ocean lane.", "expected_stance": "contradicts", "domain": "navy.mil"}
        ]
    },
    {
        "id": "eval-077",
        "claim": "Ancient Mayan stone calendars predicted the absolute physical end of planet Earth on December 21, 2012.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Smithsonian National Museum of the American Indian Maya Calendar", "url": "https://americanindian.si.edu/explore/exhibitions/item?id=823", "snippet": "The completion of the 13th Baktun in December 2012 marked the end of a calendar cycle and the beginning of a new one, not the destruction of the Earth.", "expected_stance": "contradicts", "domain": "si.edu"}
        ]
    },
    {
        "id": "eval-078",
        "claim": "A telepathic frequency from Mars transmits grocery lists directly into my neighbor radio.",
        "category": "pseudoscience_conspiracy",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },

    # ── Category 8: Economics & Public Statistics (11 cases) ──
    {
        "id": "eval-079",
        "claim": "The United States Federal Reserve was created by the Federal Reserve Act in December 1913.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Federal Reserve History: Creation of the Fed", "url": "https://www.federalreservehistory.org/essays/federal-reserve-act-signed", "snippet": "President Woodrow Wilson signed the Federal Reserve Act into law on December 23, 1913, establishing the nation central bank.", "expected_stance": "supports", "domain": "federalreservehistory.org"}
        ]
    },
    {
        "id": "eval-080",
        "claim": "The total global supply of Bitcoin is mathematically capped at 21 million coins.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Bitcoin Protocol Specification", "url": "https://en.bitcoin.it/wiki/Controlled_supply", "snippet": "Through programmatic halving of block rewards every 210,000 blocks, the total supply of Bitcoin cannot exceed 21 million.", "expected_stance": "supports", "domain": "bitcoin.it"}
        ]
    },
    {
        "id": "eval-081",
        "claim": "Hyperinflation in Weimar Germany in 1923 reached monthly inflation rates exceeding 30,000 percent.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Cato Institute: Historical Hyperinflations", "url": "https://www.cato.org/research/hyperinflation", "snippet": "Weimar Germany experienced peak monthly inflation of approximately 3.22 x 10^4 percent in October 1923.", "expected_stance": "supports", "domain": "cato.org"}
        ]
    },
    {
        "id": "eval-082",
        "claim": "The US dollar has been backed by an equivalent weight in physical gold at the Federal Reserve since 1971.",
        "category": "economics_finance",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "Federal Reserve: The End of the Gold Standard", "url": "https://www.federalreservehistory.org/essays/nixon-shock", "snippet": "In August 1971, President Richard Nixon suspended the convertibility of the US dollar into gold, ending the Bretton Woods international monetary system.", "expected_stance": "contradicts", "domain": "federalreservehistory.org"}
        ]
    },
    {
        "id": "eval-083",
        "claim": "The Gross Domestic Product (GDP) measures the monetary market value of all final goods and services produced in a country.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Bureau of Economic Analysis (BEA) GDP Definition", "url": "https://www.bea.gov/data/gdp/gross-domestic-product", "snippet": "Gross domestic product (GDP) is the value of the goods and services produced by the nation economy less the value of the goods and services used up in production.", "expected_stance": "supports", "domain": "bea.gov"}
        ]
    },
    {
        "id": "eval-084",
        "claim": "Sweden completely banned the use of physical cash by law in January 2020.",
        "category": "economics_finance",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Sveriges Riksbank: Cash in Sweden", "url": "https://www.riksbank.se/en-gb/payments--cash/cash/", "snippet": "While Sweden is a leader in digital payments, cash is not banned. The Riksdag passed legislation requiring major banks to provide cash withdrawal services.", "expected_stance": "contradicts", "domain": "riksbank.se"}
        ]
    },
    {
        "id": "eval-085",
        "claim": "A secret cryptocurrency created by my bowling league is backed by thirty tons of platinum stored in my shed.",
        "category": "economics_finance",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-086",
        "claim": "The Gini coefficient is an established statistical measure of economic inequality within a population.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "World Bank: Measuring Income Inequality", "url": "https://www.worldbank.org/en/topic/poverty/brief/measuring-inequality", "snippet": "The Gini index measures the extent to which the distribution of income among individuals deviates from a perfectly equal distribution.", "expected_stance": "supports", "domain": "worldbank.org"}
        ]
    },
    {
        "id": "eval-087",
        "claim": "The US federal minimum wage was automatically adjusted upward to $35 per hour in 2024.",
        "category": "economics_finance",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "US Department of Labor: Wage and Hour Division", "url": "https://www.dol.gov/agencies/whd/minimum-wage", "snippet": "The federal minimum wage for covered nonexempt employees has remained at $7.25 per hour since July 2009.", "expected_stance": "contradicts", "domain": "dol.gov"}
        ]
    },
    {
        "id": "eval-088",
        "claim": "Deflation is a general decrease in the price level of goods and services in an economy.",
        "category": "economics_finance",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "IMF: What Is Deflation?", "url": "https://www.imf.org/en/Publications/fandd/issues/Series/Back-to-Basics/Inflation", "snippet": "Deflation occurs when inflation turns negative, meaning the prices of most goods and services are falling over time.", "expected_stance": "supports", "domain": "imf.org"}
        ]
    },
    {
        "id": "eval-089",
        "claim": "A merchant in Cairo sold a magic carpet for four trillion dinars in cash this morning.",
        "category": "economics_finance",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },

    # ── Category 9: Adversarial & Ambiguous Logic (11 cases) ──
    {
        "id": "eval-090",
        "claim": "It is not true that water is not composed of hydrogen and oxygen.",
        "category": "adversarial_logic",
        "ground_truth_label": "true",
        "difficulty": "adversarial",
        "passages": [
            {"title": "Chemistry LibreTexts: Water Molecular Formula", "url": "https://chem.libretexts.org/Bookshelves/General_Chemistry/Water", "snippet": "Water is a chemical compound consisting of two hydrogen atoms bonded to one oxygen atom (H2O).", "expected_stance": "supports", "domain": "libretexts.org"}
        ]
    },
    {
        "id": "eval-091",
        "claim": "Although many believe sunlight is harmful, photosynthesis requires light absorption by chlorophyll pigments.",
        "category": "adversarial_logic",
        "ground_truth_label": "true",
        "difficulty": "adversarial",
        "passages": [
            {"title": "Nature Scitable: Photosynthetic Pigments", "url": "https://www.nature.com/scitable/topicpage/photosynthetic-cells-14025371/", "snippet": "Chlorophyll pigments absorb sunlight energy to drive the chemical synthesis of glucose during plant photosynthesis.", "expected_stance": "supports", "domain": "nature.com"}
        ]
    },
    {
        "id": "eval-092",
        "claim": "The exact total number of grains of sand on all Earth beaches was counted by hand to be 4,812,940,211,003.",
        "category": "adversarial_logic",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "NPR Science: How Many Grains of Sand Exist?", "url": "https://www.npr.org/sections/krulwich/2012/09/17/161096233/which-is-greater-the-number-of-sand-grains-on-earth-or-stars-in-the-sky", "snippet": "Estimates calculate roughly 7.5 x 10^18 grains of sand via mathematical volume modeling; no hand tally exists.", "expected_stance": "contradicts", "domain": "npr.org"}
        ]
    },
    {
        "id": "eval-093",
        "claim": "A completely unrecorded, secret whisper between two Roman centurions occurred in Gaul in 52 BCE.",
        "category": "adversarial_logic",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-094",
        "claim": "Drinking boiling hydrochloric acid every morning strengthens tooth enamel.",
        "category": "adversarial_logic",
        "ground_truth_label": "false",
        "difficulty": "direct",
        "passages": [
            {"title": "American Dental Association Acid Erosion Warning", "url": "https://www.ada.org/resources/research/science-and-research-institute/oral-health-topics/dental-erosion", "snippet": "Hydrochloric acid is highly corrosive and aggressively demineralizes and destroys tooth enamel and esophageal tissue.", "expected_stance": "contradicts", "domain": "ada.org"}
        ]
    },
    {
        "id": "eval-095",
        "claim": "There are exactly 24 hours in a standard solar day on Earth.",
        "category": "adversarial_logic",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "US Naval Observatory: The Solar Day", "url": "https://aa.usno.navy.mil/faq/solar_day", "snippet": "A mean solar day is defined as 86,400 SI seconds, exactly 24 hours.", "expected_stance": "supports", "domain": "usno.navy.mil"}
        ]
    },
    {
        "id": "eval-096",
        "claim": "Global stock markets will undergo an irreversible collapse on precisely November 14, 2039.",
        "category": "adversarial_logic",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-097",
        "claim": "No living organism can survive in environments without oxygen.",
        "category": "adversarial_logic",
        "ground_truth_label": "false",
        "difficulty": "nuanced",
        "passages": [
            {"title": "Microbiology by OpenStax: Anaerobic Organisms", "url": "https://openstax.org/books/microbiology/pages/9-2-oxygen-requirements-for-microbial-growth", "snippet": "Obligate anaerobes (e.g., Clostridium species) thrive exclusively in environments devoid of oxygen and are killed by oxygen.", "expected_stance": "contradicts", "domain": "openstax.org"}
        ]
    },
    {
        "id": "eval-098",
        "claim": "The chemical symbol for elemental gold is Au from the Latin word aurum.",
        "category": "adversarial_logic",
        "ground_truth_label": "true",
        "difficulty": "direct",
        "passages": [
            {"title": "Royal Society of Chemistry: Periodic Table Gold", "url": "https://www.rsc.org/periodic-table/element/79/gold", "snippet": "Gold has atomic number 79 and chemical symbol Au, derived from the Latin aurum, meaning shining dawn.", "expected_stance": "supports", "domain": "rsc.org"}
        ]
    },
    {
        "id": "eval-099",
        "claim": "A private thought occurred in Albert Einstein mind on June 4, 1912, that he never wrote down or shared.",
        "category": "adversarial_logic",
        "ground_truth_label": "unverified",
        "difficulty": "insufficient_evidence",
        "passages": []
    },
    {
        "id": "eval-100",
        "claim": "Every integer greater than 2 is the sum of two prime numbers (Goldbach Conjecture).",
        "category": "adversarial_logic",
        "ground_truth_label": "unverified",
        "difficulty": "nuanced",
        "passages": [
            {"title": "American Mathematical Society: The Goldbach Conjecture", "url": "https://www.ams.org/notices/200004/fea-goldbach.pdf", "snippet": "The Goldbach conjecture remains one of the oldest and best-known unsolved problems in number theory. It has been verified for all integers up to 4 x 10^18, but remains formally unproven.", "expected_stance": "partially_supports", "domain": "ams.org"}
        ]
    }
]

os.makedirs("tests/data", exist_ok=True)
dest_path = os.path.join("tests", "data", "labeled_benchmark_100.json")

with open(dest_path, "w", encoding="utf-8") as f:
    json.dump({"dataset_name": "TruthLens-Bench-100", "version": "1.0", "total_cases": len(cases), "cases": cases}, f, indent=2)

print(f"Generated {len(cases)} labeled benchmark cases successfully at {dest_path}")
