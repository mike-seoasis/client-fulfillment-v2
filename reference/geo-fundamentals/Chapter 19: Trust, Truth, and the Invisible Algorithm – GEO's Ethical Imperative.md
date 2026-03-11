# Chapter 19: Trust, Truth, and the Invisible Algorithm – GEO's Ethical Imperative

This quote, attributed to George Bernard Shaw, captures perfectly what’s happening in AI search today.

When ChatGPT hit 100 million users in just two months, the internet changed overnight. Search, once a static index of blue links, became conversational, generative, and unpredictable. 

The promise? 

Faster answers
Smarter discovery
Personalized journeys

But beneath that shiny interface, something deeper is unraveling.

The very systems built to democratize information are quietly destabilizing our sense of truth.

For example, a recent OpenAI report describing its latest models showed a troubling trend. On the PersonQA benchmark, the o3 model hallucinated 33% of the time (which is double the rate of its predecessor, o1). While o4-mini performed even worse, with a 48% hallucination rate. 

These figures suggest that as models grow in complexity, they’re probably also generating false information at a higher rate, raising serious concerns about how AI systems are evaluated and deployed.

The August 2025 launch of OpenAI’s GPT-5 promised significant improvements in this area, with the company claiming up to 80% fewer hallucinations compared to previous models. GPT-5’s new unified system automatically routes queries between a fast model and a deeper reasoning mode, theoretically allowing it to “think” more carefully about complex questions.

This push for more reliable AI responses reflects an industry-wide race to solve accuracy problems—Google has been pursuing a parallel approach with AI Mode, a conversational search interface powered by Gemini 2.5. AI Mode uses a “query fan-out” technique, breaking complex questions into multiple subtopics and issuing dozens of simultaneous searches to provide comprehensive answers.

Despite these competing strategies, early independent testing by Vectara’s hallucination leaderboard shows that accuracy improvement remains modest: GPT-5 achieves a 1.4% hallucination rate. 

While it’s better than GPT-4o’s 1.491% rate, it’s still higher than Gemini’s best-performing models. In other words, these improvements, which look promising in controlled testing, usually face different realities in live search environments.

These are not isolated incidents. We have AI-generated results now appearing front and center in billions of searches. Google’s AI Overviews, riddled with errors, once told users that 2025 is still 2024 and that astronauts have met cats on the moon. 

These might look like harmless mistakes, but when you zoom in, they represent systemic failures that shape what people believe to be true. When falsehoods are delivered with confidence, repeated at scale, and surfaced by default, they legitimize misinformation.

For those of us working in SEO, marketing, content strategy, and digital experience, this changes everything.

While search is still about relevance, the way we achieve it is shifting. In an AI-first world, the fight for visibility is now entangled with the fight for truth, and that’s where Generative Engine Optimization (GEO) comes in.

GEO represents a new layer built on top of traditional journalistic and content creation principles. Rather than discarding decades of proven SEO fundamentals, GEO extends these foundations to work within probabilistic, AI-mediated discovery environments. So while the core tenets of quality content creation remain intact, it basically requires additional considerations for how machines interpret, synthesize and present information to users. 

You can also think of GEO in terms of not just optimizing for visibility, but for representation, verifiability, and trust in the age of synthetic search, where language models generate the interface, the answer, and the context itself.

In this chapter, we’ll explore how hallucination, misinformation, and corporate opacity are colliding with the mechanics of SEO, and why GEO must evolve not only as a strategy, but as a safeguard.

CITATION WITHOUT ACCURACY: THE GREAT DECEPTION

The problem isn’t exactly about AI systems making mistakes. The issue is doing it confidently and citing what looks like credible references to support completely false claims.

​​One of the most visible examples came in 2024 when Google’s AI Overviews suggested adding an “eighth of a cup of nontoxic glue” to pizza so the cheese would stick. The system pulled this from an 11-year-old Reddit joke comment and presented it as legitimate cooking advice. It has also suggested bathing with toasters, eating rocks, and following unvetted medical suggestions pulled from anonymous forums.

Source: Search Engine Land

These funny-looking responses constitute structural failures rooted in how large language models are trained. By scraping the open web without strict source prioritization, generative systems give as much weight to offhand jokes on Reddit as they do to peer-reviewed studies or government advisories. The result is citation without accuracy, which is a convincing performance of authority that often lacks any.

The bigger picture reveals a threat that goes beyond simple factual errors. AI systems can also distort perception in ways that have direct commercial impact. 

For example, if your brand isn’t already highly visible and well-documented online, you’re vulnerable to having your reputation defined by incomplete or biased information. This can happen when a SaaS company with limited bottom-of-funnel content faces a competitor who publishes a comparison piece that subtly undermines their product by framing it as slow, overpriced, or missing key features.

If that narrative is picked up by Google’s AI Overviews or ChatGPT, it can be repeated as though it’s consensus truth. The reason is simple—the model isn’t fact-checking, rather it’s pattern-matching. And those patterns may be coming from a single competitor blog post, a five-year-old Reddit comment, or a lone disgruntled review. In the process, subjective opinion calcifies into “authoritative” AI-generated advice, shaping buyer perception before they’ve even visited your site.

Even worse, these AI systems may hallucinate features or flaws entirely out of thin air.

One striking real-world case comes from Soundslice, a sheet music SaaS platform, where its founder, Adrian Holovaty, noticed a wave of unusual uploads in the company’s error logs consisting of screenshots of ChatGPT chats containing ASCII guitar tablature. 

Source: Arstechnica

It turned out ChatGPT was instructing users to sign up for Soundslice and import ASCII tabs to hear audio playback, but there was just one problem: Soundslice had never supported ASCII tab, meaning the AI had invented the feature out of thin air while setting false expectations for new users and making the company look as if it had misrepresented its own capabilities. In the end, Holovaty and his team decided to build the feature simply to meet this unexpected demand, a decision he described as both practical and strangely coerced by misinformation.

This case explains the deeper structural risk we talk about. When AI-generated answers become the default interface for discovery, every brand (especially those without strong, persistent visibility) runs the risk of being inaccurately defined, whether by outdated content, competitor bias, or outright invention.

The fact that generative systems don’t weigh intent, credibility, or context is not helping issues either. Models instead prioritize statistical patterns over source quality. Patterns here imply:

AI systems learn to mimic the look and feel of credibility, even when the substance isn’t there. 
They cite sources, but misread them. 
They quote facts, but strip out caveats. 
They frame content to sound rigorous, while undermining its core accuracy. 
And they do it all with a tone of effortless confidence.

Once these flawed outputs dominate the search interface, the consequences snowball. Misrepresented brands lose clicks. Publishers lose traffic. Fact-checking resources shrink. And that degraded content feeds back into the next generation of AI models, accelerating a feedback loop that rewards volume over veracity.

Winning visibility (as per GEO) now means safeguarding how your brand is represented in the synthetic layer of search. If you’re not shaping the inputs, you risk losing control over the outputs.

UNDERSTANDING THE HALLUCINATION EPIDEMIC

In the early days of AI, generating human-like text was a breakthrough. Now, that same ability has become one of its greatest liabilities. What computer scientists call “hallucinations” are essentially falsehoods delivered with undue confidence and scaled across the internet.

These AI systems are not just wrong; they are wrong in ways that feel persuasive, familiar, and difficult to fact-check in real time.

And the problem is everywhere. One study by researchers at Stanford and other institutions found that AI legal research tools from LexisNexis and Thomson Reuters hallucinated in 17% to 33% of responses. 

Source: Stanford HAI

These AI legal tools hallucinated by either stating the law incorrectly or citing correct information with irrelevant sources. The latter is even more detrimental, as it could mislead users who trust the tool to identify authoritative sources.

Medical data shows similar risks. Even advanced models hallucinate at rates ranging from 28% to over 90% in medical citations. Some of these figures may sound insignificant, but when AI systems handle billions of queries, the number of false or harmful recommendations reaches into the tens of millions daily.

This problem bleeds into SEO. As AI-generated answers become more visible in SERPs, hallucinations are no longer confined to fringe use cases. They are embedded in the way information is being delivered to mainstream audiences. 

In March 2025, Semrush reported that 13.14% of all queries triggered AI Overviews, nearly doubling from just two months prior. 

That increase was most dramatic in sensitive categories like health, law & government, people & society, and science—the very spaces where accuracy matters most.

The Semrush author remarks, “It’s surprising to see Google roll out AI Overviews so aggressively in three industries that so often lack consensus answers and come with more than their fair share of regulatory pressure and misinformation risks.”

Google may be getting more confident in the accuracy of its answers, but the fact remains: as more users begin to treat AI-generated answers as definitive, the risk that false information gets amplified grows exponentially.

This creates a dangerous contradiction. Traditional SEO practices were built on credibility, relevance, and authority. But AI-powered summaries often pull fragments out of context or merge them into synthetic responses that no longer reflect the original intent of the content. 

In terms of GEO, your brand may be cited, but not accurately. And once that distorted version is presented in any AI platform, any information shown would almost always twist the perception of your audience.

Now, GEO is not a workaround for hallucinations, but rather a framework for minimizing their impact. It emphasizes precision, clarity, and structural cues that help generative systems extract the right information from your content. 

That might mean:

Writing with unambiguous intent
Strengthening factual signals through verified citations, schema markup, and clearly defined entities
Understanding how LLMs interpret language differently from humans or traditional search crawlers

By optimizing for interpretability as much as visibility, GEO increases the chances that what gets surfaced in AI summaries reflects the truth, not a distorted version of it. It gives publishers and brands a fighting chance to steer AI outputs toward reliability. 

It’s not a guarantee, but it’s a guardrail. And in an environment where hallucinations are inevitable, that guardrail may be the only thing protecting users (and their reputations) from harm.

REGULATION AND TRANSPARENCY IN SEARCH SYSTEMS

AI search has introduced a new type of opacity, where users ask a question, receive a seemingly human response, and rarely question the source. This answer just appears, often convincingly worded yet sometimes confidently wrong, and the invisible architecture behind it often buries or omits the original source entirely. 

Even when citations or links are provided, they’re frequently hidden behind dropdowns, scattered across the page, or attached to only part of the answer. In practice, the AI’s polished, complete-sounding response still overshadows the source itself, making verification an afterthought rather than the default.

This creates a critical disconnect where the model’s confidence does not match the reliability of its inputs, leading to a fracture in user trust. 

We are now grappling with systems that perform truth rather than presenting it, which is why the conversation around transparency is moving from theory to practice, becoming a structural requirement for digital knowledge systems to function safely.

Google’s own Search Quality Rater Guidelines (SQRG) provide the closest thing SEO professionals have to a regulatory compass, placing particular weight on E-E-A-T (Experience, Expertise, Authoritativeness, and Trustworthiness). 

The emphasis is especially sharp for topics involving health, finance, civic processes, and legal matters, precisely the areas where hallucinations and misinformation are most damaging. 

While search systems are internally evaluated on their verifiability, this process is not externally visible to users. Without access to citations, accuracy ratings, or the model’s reasoning, users are prone to accepting AI-generated summaries as authoritative, an assumption that is often incorrect.

And this is where GEO has a critical role to play, evolving from a reactive tactic into a forward-facing discipline where transparency is paramount. 

Transparency in this context means designing content that inherently explains its own authority, structuring pages to show why something is true, and using specific markup to help machines distinguish between speculation and certainty.

These practices are no longer hypothetical but are becoming table stakes for digital visibility, as building content in a way that its integrity is obvious to both a human reader and a machine is essential. This includes providing clear inline citations, offering author bios that establish expertise, and using structured data to explicitly define the nature of the information presented.

iPullRank has already written extensively about how these guidelines overlap with real-world SEO strategies. For example, our breakdown of the Google algorithm leak shows that signals like site authority, click satisfaction, and user behavior patterns all contribute to how Google interprets source quality. 

This technical validation shows that ethical AI practices actually matter for visibility, not just principles. When Google measures content originality, author information, and how users engage with content, the responsible AI approaches we use become important factors. 

Yet in AI search, these standards are still voluntary. Platforms aren’t required to disclose how an answer was generated, which sources it relied on, or why certain context was chosen over others. There’s no accountability for the accuracy or transparency of the information that surfaces. 

As a result, the brands that invest in building verifiable, high-quality content often compete on the same level as those who don’t—leaving the integrity of search results up to opaque model behavior rather than proven authority.

This brings us full circle. Transparency is a fundamental architecture, not merely a checkbox on a list of best practices. In a world where AI decides what users see, how sources are interpreted, and what information is prioritized, we can no longer afford to build content for humans alone. 

Recognizing this challenge, leading AI companies, such as Anthropic, OpenAI, and Google,  have begun investing in research transparency and value alignment initiatives. For those seeking to understand how these systems actually work and what safeguards exist, several key resources provide direct access to safety research and transparency reporting:

 

Organization 

 

Resources & Focus




Anthropic

 

Research – To investigate the safety, inner workings, and societal impact of AI models


 

Transparency Hub – To study Anthropic’s key processes and practices for responsible AI development


 

Trust Center – For monitoring security practices and compliance standards


  


Google

 

AI Research – For exploring machine learning breakthroughs and applications across multiple domains


 

Responsible AI – To observe AI in relation to fairness, transparency, and inclusivity


 

AI Safety – To understand AI’s role in delivering safe and responsible experiences across different products


  


OpenAI

 

Research for following model development and capability advances


 

Safety for reviewing system evaluations and risk assessment frameworks


  


Academic

 

arXiv.org for accessing the latest AI research papers and preprints

These resources help explain what we’re working with. But understanding the systems is just the first step.

We must build content for machines to read correctly, and for readers to trust what they see. The path forward is not simply more AI content; it is better content, built for interpretability, authority, and trust. GEO provides the lens, but trust is still the ultimate goal.

THE PATH FORWARD

The invisible algorithm’s most visible impact may be whether we choose to engineer relevance responsibly or allow the machines to engineer our reality for us. The stakes extend far beyond marketing metrics. We risk building a generation’s worth of technology atop a foundation that is deeply vulnerable.

The choice before us is clear: We can continue treating AI search as a technological inevitability to be gamed, or we can recognize it as an ethical challenge requiring systematic solutions. The emergence of GEO and Relevance Engineering represents more than a new marketing discipline; it’s a necessary evolution toward more responsible, trustworthy, and effective information systems.

The algorithms powering AI search may be invisible, but their impact on truth, trust, and society is becoming undeniably visible. Success in this new environment requires not just technical expertise, but a commitment to accuracy, transparency, and responsibility.

The future of search is about being discovered as well as trusted, and in a world where AI increasingly stands between what we ask and the knowledge we receive, that trustworthiness isn’t just a competitive advantage, it’s an ethical imperative.
