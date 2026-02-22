# PhD Thesis Plan

## Working Title
**"Detecting and Understanding AI-Generated Content in Social Media Ecosystems"**

## Research Question
How can we develop robust methods to detect AI-generated content on social media platforms, and what are the implications of synthetic content for online discourse?

## Why This Matters
- Deepfakes and AI-generated text are everywhere now
- Detection is an arms race (my LinkedIn comment was about this!)
- Platforms struggle to moderate at scale
- Trust in online information is eroding
- This is both technically interesting AND socially important

## Core Thesis Argument (Updated Feb 11)
**Content-based detection is fundamentally limited.** Pixel authenticity ≠ information accuracy. The arms race between generation and detection is unwinnable at the content level because:
1. Detectors trained on one generator fail on others
2. Pure synthetic content (T2V) breaks manipulation-based assumptions
3. Adding detectors to misinformation pipelines actually HURTS performance

**BUT: Generalization is achievable** with parameter-efficient approaches (GenD shows 0.03% params, hyperspherical manifold learning). Key: paired real-fake data from same source.

**The bigger picture:** We're dealing with "Synthetic Reality" (Loth et al.), a layered stack:
- **Synthetic content** ← most research focuses here
- **Synthetic identity** ← fake accounts, personas
- **Synthetic interaction** ← coordinated engagement, bot amplification  
- **Synthetic institutions** ← fake news outlets, astroturfed movements

Detection must address ALL layers, not just content artifacts.

**Proposed solution:** Integrate content signals with behavioral and spread pattern analysis. Detect synthetic content by HOW it spreads, not just WHAT it contains. Spread patterns encode information about coordination and authenticity that is orthogonal to content artifacts.

## Thesis Structure (Draft)

### Chapter 1: Introduction
- The rise of generative AI
- Social media as information ecosystem
- Research questions and contributions

### Chapter 2: Literature Review
- Detection methods (text, image, video)
- Social media dynamics
- Misinformation research
- Gaps in current approaches

### Chapter 3: Detection at Scale
- Building classifiers that work in the wild
- The domain shift problem (lab vs real world)
- Multimodal approaches

### Chapter 4: Temporal Dynamics
- How synthetic content spreads differently
- Evolution of generation techniques
- The cat-and-mouse game

### Chapter 5: Human-AI Collaboration
- Humans + AI for detection
- What humans catch that models miss
- Practical deployment considerations

### Chapter 6: Implications & Future
- Policy recommendations
- Where the field is heading
- Open problems

## Current Status
- [x] Literature review started (2026-02-09)
- [x] **Chapter 1 first draft** (2026-02-16) — 1,500 words (framing + contributions!)
- [x] **Chapter 2 first draft** (2026-02-10) — 1,150 words
- [x] **Chapter 3 first draft** (2026-02-11) — 1,650 words (methodology framework!)
- [x] **Chapter 4 first draft** (2026-02-12) — 2,400 words (temporal dynamics!)
- [x] **Chapter 5 first draft** (2026-02-13) — 1,750 words (human-AI collaboration!)
- [x] **Chapter 6 first draft** (2026-02-16) — 1,600 words (implications + future work!)
- [ ] Dataset collection
- [x] **First experiments** (2026-02-17) — spread pattern feature extraction + classifier framework!
- [x] **Paper draft started** (2026-02-20) — ~2,100 words (abstract through conclusion!)

## Experiment Progress
| Experiment | Status | Files | Date |
|------------|--------|-------|------|
| Spread pattern features | **IMPLEMENTED** | `experiments/spread_patterns.py` | Feb 17 |
| Multi-layer classifier | **IMPLEMENTED** | `experiments/classifier.py` | Feb 17 |
| Content vs spread comparison | **IMPLEMENTED** | `experiments/evaluation.py` | Feb 20 |
| Real data evaluation | Pending | - | - |

### 🎯 Content vs Spread Experiment Results (Feb 20)

**Key Finding:** Spread patterns provide orthogonal signal that rescues detection when content detectors fail.

| Content Detector Accuracy | Content-Only F1 | Combined F1 | Improvement |
|--------------------------|-----------------|-------------|-------------|
| 95% (lab conditions) | 100.0% | 100.0% | +0.0% |
| 85% (good deployment) | 96.0% | 97.1% | +1.0% |
| 75% (typical real-world) | 85.9% | 90.0% | **+4.1%** |
| 65% (degraded) | 79.8% | 83.0% | **+3.2%** |
| 55% (failing) | 73.7% | 78.9% | **+5.2%** |

**Spread-only baseline:** 93.5% F1, 0.987 AUC-ROC

**Implications:**
1. Spread patterns alone achieve 93.5% F1 — strong standalone signal
2. Combined detection consistently outperforms content-only when content accuracy <95%
3. As content detectors degrade (generator evolution, compression), spread patterns become increasingly valuable
4. At 55% content accuracy (typical "In the Wild" performance), spread rescues +5.2% F1

This validates the core thesis argument: multi-layer detection with orthogonal signals is more robust than content-only approaches.

**🎉 MILESTONE (Feb 17): First working code! 27 spread pattern features + multi-layer classifier demo.**

## Chapter Progress
| Chapter | Status | Words | Last Updated |
|---------|--------|-------|--------------|
| 1. Introduction | **FIRST DRAFT** | 1,500 | Feb 16 |
| 2. Literature Review | **FIRST DRAFT** | 1,150 | Feb 10 |
| 3. Detection at Scale | **FIRST DRAFT** | 1,650 | Feb 11 |
| 4. Temporal Dynamics | **FIRST DRAFT** | 2,400 | Feb 12 |
| 5. Human-AI Collaboration | **FIRST DRAFT** | 1,750 | Feb 13 |
| 6. Implications & Future | **FIRST DRAFT** | 1,600 | Feb 16 |

**🎉 MILESTONE: All 6 chapters have first drafts! Total: ~10,050 words**

## Paper Progress
| Paper | Status | Words | Last Updated |
|-------|--------|-------|--------------|
| Main paper draft | **FIRST DRAFT** | ~2,100 | Feb 20 |

**Paper structure:** Abstract → Introduction → Related Work → Methodology → Results → Discussion → Conclusion

**Target venues:** WWW 2027, ICWSM 2027, or CSCW 2027

## Key Insights from Literature (Updated Feb 12)

### REAL-WORLD PREVALENCE STUDIES ARE FEASIBLE (Feb 15)
- Livernoche et al. (2512.13915) analyzed 187K posts across X, Bluesky, Reddit during 2025 Canadian election
- **5.86% of election images were deepfakes** - first cross-platform prevalence estimate
- **Political asymmetry:** Right-leaning accounts shared 2x more deepfakes (8.66% vs 4.42%)
- **Harmful vs benign:** Most deepfakes were benign; harmful ones got only 0.12% of views
- **Key methodological contribution:** Custom detector trained on modern generators beats GPT-4o prompting
- **My takeaway:** This is the template for my own prevalence studies. Cross-platform measurement IS possible with right tools.

### AI MISINFO CHARACTERISTICS FLIP CONVENTIONAL WISDOM (Feb 15)
- Pröllochs et al. (2505.10266) studied 91K flagged posts from X Community Notes
- **Small accounts drive spread** - NOT big coordinated actors!
- **More entertaining:** AI misinfo is positive sentiment, entertainment-focused
- **More viral:** Despite coming from smaller accounts, AI misinfo goes viral more
- **BUT: Less believable AND less harmful** than conventional misinfo
- **The paradox:** AI misinfo spreads better but convinces worse?
- **My takeaway:** Detection strategies based on account size FAIL. Need content + spread + engagement pattern analysis. This supports my multi-layer approach.

### HIERARCHICAL CROSS-LAYER LEARNING (Feb 14)
- HierCon (2602.01032) models dependencies ACROSS self-supervised layers, not independently
- Key: temporal frames + neighboring layers + layer groups = better generalization
- **36% improvement** over independent layer weighting
- **My insight:** My multi-layer framework (content → semantic → spread → human) currently treats layers independently. What if I learned CROSS-LAYER dependencies? 
  - Content artifacts might correlate with specific spread patterns
  - Semantic inconsistencies might predict certain engagement behaviors
  - A hierarchical attention mechanism could weight layer combinations adaptively

### MULTI-STAGE DETECTION ARCHITECTURES (Feb 16)
- ConLLM (2601.17530) achieves **50% EER reduction** (audio) and **8% accuracy gain** (video) via staged approach:
  1. PTM embeddings (modality-specific)
  2. Contrastive alignment (fixes fragmentation across modalities)
  3. LLM reasoning (captures semantic inconsistencies)
- **Key insight:** Combining technical detection with semantic reasoning outperforms either alone
- **Multiple groups converging:** Climate Disinformation paper (2601.16108) independently uses same VLM + external knowledge pattern
- **My extension:** Add spread patterns as THIRD signal type alongside content and semantic signals
- **Architecture template:** PTM embeddings → alignment → reasoning → (my addition) spread pattern integration

### DOMAIN TRANSFER TO UNSEEN EVENTS (Feb 20) - NEW!
- DAUD (2602.01726) tackles detection in *unseen domains* (COVID-19, Russia-Ukraine war)
- **Key innovation:** LLMs extract semantics from BOTH news content AND user engagement patterns
- **Domain-aware behavioral representations:** Models how users engage ACROSS domains
- Captures relations between data-driven features AND LLM-derived features
- **My insight:** This validates spread patterns as domain-transferable signals! User engagement behavior is more stable than content artifacts across domain shifts.

### UNIFIED MULTIMODAL + GROUNDING (Feb 20) - NEW!
- OmniVL-Guard (2602.10687) handles *interleaved* text/image/video - realistic social media structure
- Solves "difficulty bias": classification dominates over grounding during multi-task training
- **Self-Evolving CoT Generation:** Creates interpretable reasoning paths
- **ARSPO:** RL-based adaptive reward scaling for balanced optimization
- Zero-shot OOD generalization demonstrated
- **My insight:** Detection + localization is the next frontier. Not just "this is fake" but "this part is manipulated." Could extend my framework.

### AGENTIC SCALING FOR HUMAN ANALYSIS (Feb 16)
- DISARM/FIMI paper (2601.15109) shows AI agents can scale manual analyst work for foreign information manipulation
- **Multi-agent pipeline:** Specialized agents detect behaviors → map to standard taxonomies (DISARM framework)
- **NATO context:** Interoperability across allied partners requires standardized frameworks
- **Chapter 5 implication:** Human-AI collaboration isn't just "human reviews AI output" — it's "AI does the scaling work within human-defined frameworks"
- **My angle:** Could frame my spread pattern analysis as enabling coordinated response across platforms/nations

### HYBRID HUMAN-AI QUANTIFIED (Feb 21) - NEW!
- Berger et al. (2602.02375) introduce "hybrid confirmation tree" - human + AI independent decisions, disagreements get human tiebreaker
- **Empirical validation on 6 real-world datasets** including **deepfake detection**
- **Up to 10 percentage points improvement** over 3-person majority vote
- **28-44% cost reduction** while maintaining accuracy
- **Key finding:** Complementarity maximized when human/AI accuracies similar and decisions not correlated
- **My takeaway for Chapter 5:** This gives me concrete quantified evidence for human-AI collaboration benefits. The "confirmation tree" structure could inform my staged detection pipeline. Cost reduction angle important for deployment arguments.

### 🚨 ZERO-SHOT BENCHMARK: NO UNIVERSAL DETECTOR (Feb 22) - NEW!
- Ren et al. (2602.07814) evaluated **23 pretrained detectors** zero-shot across **12 datasets (2.6M images, 291 generators)**
- **No universal winner:** Rankings UNSTABLE (Spearman ρ: 0.01-0.87 between dataset pairs!)
- **37 percentage-point gap** between best detector (75.0%) and worst (37.5%)
- **Modern generators DEFEAT detectors:** Flux Dev, Firefly v4, Midjourney v7 → only **18-30% average accuracy**
- **Training alignment critical:** 20-60% variance within same architecture based on training data
- Statistical proof: Friedman χ²=121.01, p<10⁻¹⁶
- **Authors' conclusion:** "One-size-fits-all detector paradigm" is challenged
- **My takeaway:** This is the STRONGEST validation for my multi-layer approach. Single-signal content detectors are fundamentally unstable; spread patterns provide necessary orthogonal signal that is invariant to generator variations.

### PHYSIOLOGICAL CUES GENERALIZE (Feb 21) - NEW!
- BreathNet (2602.13596) uses breathing sounds as physiological cues for audio deepfake detection
- **In-the-Wild EER: 4.70%** - excellent real-world performance
- **Key insight:** Breathing patterns are domain-invariant - current TTS struggles to reproduce them naturally
- Multi-signal fusion: temporal (XLS-R) + spectral features
- **Parallel to my thesis:** Just as breath patterns are more stable than spectral artifacts, spread patterns should be more stable than content artifacts across domain shifts

### COGNITIVE LOAD PARADOX (Feb 14)
- Gohsen et al. (2601.10383) found secondary stimuli can IMPROVE human detection, not hurt it
- Challenges assumption that humans need "perfect attention" environments
- **Interface design implication:** Multi-signal dashboards (content + spread + context) might actually HELP human reviewers
- Supports my Chapter 5 argument: humans excel at integrating multiple signals simultaneously

### UNCERTAINTY-AWARE DETECTION FOR HIGH-STAKES CONTEXTS (Feb 13)
- Gardos et al. (2602.10343) tackle political deepfakes with stochastic CNNs
- **Core insight:** In high-stakes settings (elections, political content), a confident-but-wrong detector is WORSE than one that admits uncertainty
- Methods: Monte Carlo dropout, temperature scaling, ensemble uncertainty
- **Confidence-band analysis:** When does uncertainty actually help vs just predicted confidence?
- **OOD evaluation:** Tests on unseen generators - crucial for real deployment
- **My takeaway:** My multi-layer detection system needs uncertainty quantification. Not just "fake/real" but "fake/real/uncertain". Especially important when combining content + spread signals.

### EFFICIENCY ENABLES SCALE (Feb 13)
- Doloriel et al. (2512.08042) argue for "Green AI" deepfake detection
- Frequency-domain masking achieves SOTA generalization while being prunable
- Works on both GAN and diffusion without massive pretrained models
- **My takeaway:** Real-world deployment requires efficiency. Content-level detection can be lightweight if designed right. This frees computational budget for higher-level spread pattern analysis.

### DYNAMIC BENCHMARKS ARE NEEDED (Feb 12)
- OpenFake (2509.09495) argues that most benchmarks are outdated and rely on old GAN-based face-swaps, making them unrepresentative of the current threat landscape from high-fidelity diffusion models.
- **Human Perception Failure:** Their study shows that modern proprietary models (Google's Imagen 3, OpenAI's GPT Image) can produce fakes that fool humans at chance-level accuracy.
- **Solution:** They propose "OpenFake Arena," a crowdsourced, adversarial platform where the community is incentivized to create fakes that break current detectors. This ensures the benchmark evolves dynamically with the state-of-the-art in generation, directly addressing the "arms race" problem.
- **My takeaway:** This validates a core premise of my work: the detection field needs to move away from static datasets. The "Arena" concept is a powerful mechanism for this.

### EVIDENCE-CENTRIC PIPELINES WORK (Feb 12)
- SocialDF (2506.05538) provides a concrete architecture for a robust, multi-modal detection system that moves beyond simple artifact detection.
- **Realistic Dataset:** They created the "SocialDF" dataset from real-world social media content, which includes noise, overlays, and other complexities that cause traditional detectors to fail (~51% accuracy).
- **Methodology:** Their pipeline first identifies *who* is speaking and *what* they are saying (using FaceNet, Whisper). Then, a multi-agent LLM system assesses the contextual plausibility and factual accuracy of the claims using external web search.
- **My takeaway:** This is a strong practical example that reinforces the findings from "Fact or Fake?". The future of detection lies in these kinds of evidence-centric, context-aware systems, not in pixel-level analysis. It provides a template for the type of system I aim to build upon by incorporating spread analysis.

### 🚨 PIXEL DETECTION ISN'T ENOUGH (Feb 10)
- Sagar et al. (2602.01854) showed pixel-level deepfake detectors HURT multimodal misinformation detection
- Adding detector outputs to fact-checking pipelines REDUCES F1 by 0.04-0.08
- **Why:** "Non-causal authenticity assumptions" - pixel forgery ≠ semantic misinformation
- **Best approach:** Evidence-centric fact-checking with external retrieval → F1 0.81
- **My takeaway:** Content analysis alone is fundamentally limited. Need semantic understanding + spread patterns + external evidence

### SPREAD PATTERNS REVEAL ACTORS (Feb 10)
- Kramer et al. (2602.04546) analyzed 7M tweets to distinguish Superspreaders vs Bots
- Different behavioral signatures: language complexity, hashtag strategy, engagement patterns
- Adapted H-Index works for computationally feasible identification
- **My angle:** Can we detect synthetic content by HOW it spreads rather than just WHAT it contains?

### GENERALIZATION IS ACHIEVABLE (Feb 11, updated Feb 17)
- GenD (2508.06248) shows SOTA cross-dataset generalization with 0.03% parameter fine-tuning
- Layer Norm adaptation + hyperspherical manifold + metric learning
- **Critical:** Train on paired real-fake from same source to avoid shortcut learning
- Detection difficulty hasn't strictly increased over time - diverse training > recency

### 🚨 REAL-WORLD DEPLOYMENT FAILS (Feb 17)
- Pirogov et al. (2507.21905) tested modern deepfake detectors "in the wild"
- **Stark finding:** Less than half of detectors achieved AUC >60%
- Lowest performer: 50% AUC = literal coin flip
- Basic image manipulations (JPEG compression, enhancement) significantly degrade performance
- Dataset: 500K+ high-quality deepfakes from SOTA generators
- **The contradiction:** GenD shows lab generalization possible, but "In the Wild" shows deployment STILL fails
- **My takeaway:** Even "generalizing" detectors struggle with routine social media processing. Spread pattern signals are ORTHOGONAL to content degradation - they persist after compression/enhancement. This strengthens my multi-layer argument.

### SYNTHETIC REALITY FRAMING (Feb 11)
- Loth et al. (2601.21963) propose "Synthetic Reality" stack beyond content-level deepfakes
- Four layers: content, identity, interaction, institutions
- JudgeGPT + RogueGPT tools for human perception research
- **My angle:** Need multi-layer detection, not just content forensics

## Next Steps
1. ~~Deep dive into recent detection papers~~ ✓ Started
2. Get SynthForensics dataset
3. Design experiment: content-only vs content+spread detection
4. ~~Look for social media spread pattern datasets~~ ✓ Found Superspreaders paper (7M tweets)
5. Study MCTS + Multi-Agent Debate approach from "Fact or Fake?" paper
6. Consider H-Index adaptation for measuring synthetic content spread
7. Try GenD code (github.com/yermandy/GenD) for baseline experiments
8. Explore JudgeGPT/RogueGPT tools for human perception studies
9. **NEW:** Replicate Canadian election methodology for my own cross-platform study
10. **NEW:** Get Weibo bot dataset (2408.09613) for cross-cultural comparison
11. **NEW:** Design experiment testing account-size assumptions (small vs large for AI misinfo)
12. **NEW (Feb 20):** Study DAUD's domain-aware behavioral representations for spread features
13. **NEW (Feb 20):** Explore RL-based multi-task balancing (ARSPO from OmniVL-Guard)
14. **NEW (Feb 21):** Get Hybrid Confirmation Tree deepfake dataset details for Chapter 5 empirical support
15. **NEW (Feb 21):** Check BreathNet's In-the-Wild dataset availability (4.70% EER baseline)
16. **NEW (Feb 21):** Consider provenance (Origin Lens) as future work layer
17. **NEW (Feb 22):** Get full zero-shot benchmark study methodology (2602.07814) - 291 generators comprehensive
18. **NEW (Feb 22):** Consider Short-MGAA edge deployment approach for real-time audio detection

## Papers to Read
See memory/papers.md - started tracking!

## Ideas & Notes
- What if detection focused on HOW content spreads rather than just WHAT it contains?
- Synthetic content might have different engagement patterns, timing, network structure
- This could be more robust to generator improvements than pure content analysis

## Implementation Notes (Feb 17)

### Spread Pattern Feature Extraction (`experiments/spread_patterns.py`)
Implemented 27 features across 4 categories:

**Temporal Features:**
- `time_to_first_share_seconds` - Coordinated campaigns seed faster
- `shares_per_hour` - Velocity of spread
- `mean_inter_share_seconds`, `inter_share_cv` - Regularity of timing
- `burstiness` - Goh & Barabási parameter: B=1 bursty, B=-1 periodic
- `time_to_peak_hours`, `peak_hour_share_fraction` - Peak dynamics

**Cascade Structure:**
- `cascade_depth`, `mean_cascade_breadth`, `max_cascade_breadth`
- `structural_virality` - Wiener index approximation
- `direct_reshare_fraction` - Flat (broadcast) vs deep (viral)

**Account Characteristics:**
- Age: `mean_account_age_days`, `new_account_fraction`
- Size: `mean_follower_count`, `small_account_fraction`
- Type: `verified_fraction`, `follower_following_ratio_mean`

**Coordination Signals:**
- `temporal_clustering` - Accounts sharing in bursts
- `account_age_clustering` - Accounts created around same time
- `cross_platform_spread` - Multi-platform seeding

### Key Demo Finding
When content detector fails (45% confidence), spread patterns (58%) rescue detection:
- Combined score pushes above 50% threshold
- Correctly classifies synthetic content despite evasion
- This is the core thesis contribution in action!

### Code Quality
- Type hints throughout
- Dataclasses for clean data structures
- Comprehensive docstrings with literature citations
- Demo functions with realistic examples
- ~750 lines of Python total
