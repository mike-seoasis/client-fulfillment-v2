# Chapter 15: Simulating the System for GEO Insights

In traditional SEO, our optimization work has always been reactive to the realities of a live system. Google pushes an update, rankings shift, we interpret the movement through ranking data, and we adjust. But the Generative Engine Optimization paradigm demands a more proactive stance. The search systems we’re optimizing for, like Perplexity, Copilot, Google AI Overviews, and others, are no longer static indexes queried via a fixed lexical interface. They are multi-stage reasoning systems with hidden retrieval layers, generative models, and filtering mechanisms. If we want to reliably influence these systems, we need to stop treating them as black boxes and start building simulators.

Simulation in GEO is not just an academic exercise. It is a practical, iterative process for probing how an AI-driven search environment sees, interprets, and ultimately chooses to present your content. The methods range from LLM-based scoring pipelines to synthetic query generation, retrieval testing, and even prompt-driven hallucination analysis. The objective is simple: replicate enough of the retrieval and reasoning stages that you can meaningfully test hypotheses before shipping content into the wild.

Why Simulation Matters in GEO

The stakes are higher now because AI search systems are less predictable than classical ranking pipelines. In a purely lexical search environment, you could infer retrieval logic from keyword patterns, backlinks, and document structure. In GEO, you’re working with vector spaces, transformer encoders, entity linking algorithms, and retrieval-augmented generation orchestration layers. Every stage introduces potential nonlinearities or small changes in content can produce outsized effects, or no effect at all, depending on where the bottleneck lies.

Simulation offers two key advantages.

1. It lets you isolate variables. If you can feed synthetic queries into a controlled retrieval model and observe which passages surface, you can decouple retrieval influence from generative synthesis quirks. This is effectively what was done with Perplexity in the original [Generative Engine Optimization paper]().
2. It shortens the feedback loop. Rather than waiting for a production AI system to refresh its indexes or re-embed your pages, you can pre-test adjustments against a local or cloud-hosted model and iterate in hours instead of weeks.

Forward-Looking Opportunity: As AI search platforms mature, we are likely to see more frequent architectural changes to their retrieval layers. We can expect new embedding models, updated entity-linking heuristics, and modified context window sizes. A robust simulation environment will not only help adapt to these shifts, it could become a core competitive moat: the better your internal model of a given AI search surface, the faster you can exploit new ranking levers.

Building a Local Retrieval Simulation App with LlamaIndex

One of the most powerful ways to understand how your content performs in a RAG setup is to build your own lightweight simulation environment. This lets you feed in a query and a page (or just its text) and see exactly which chunks the retriever selects to answer the question.

We’ll walk through building a Google Colab or local Python app that uses:

* Trafilatura for HTML-to-text extraction from URLs
* LlamaIndex for chunking, indexing, and retrieval simulation
* FetchSERP for getting real AI Overview / AI Mode rankings for comparison

The tool will output:

* Retrieved chunks list — the exact text blocks your simulated retriever would pass to the LLM.
* Overlap analysis — how those chunks compare to live AI Search citations.
* Diagnostic chart — a simple visualization of chunk relevance scores.

Here’s how we’ll do it.

Step 1 — Install Dependencies

Get your Python environment ready with LlamaIndex, Trafilatura, FetchSERP, and Gemini embeddings.

Step 2 — Set Up Your API Keys

Authenticate with FetchSERP, Gemini, and any LLM provider so your workflow can run end-to-end.

You’ll need:

* FetchSERP API key — from [https://fetchserp.com]()
* GEMINI API key — for embeddings and LLM queries in LlamaIndex

Create a .env file to store your API credentials:

Step 3 — Extract the Content

Pull clean, structured text from a target URL using Trafilatura for optimal indexing.

If the user doesn’t have a URL, you can accept raw pasted copy instead.

Step 4 — Index with LlamaIndex

Embed and store your content chunks using Gemini’s gemini-embedding-001 model for precise retrieval.

This builds an embedding index from your content. LlamaIndex automatically chunks the text and stores embeddings for retrieval.

Step 5 — Simulate Retrieval

Run a query through your local index to see which chunks a retriever would surface.

This returns the top 5 chunks that would be fed into the LLM for a RAG answer.

Step 6 — Get Real AI Search Data for Comparison

Use FetchSERP to pull AI Overview or AI Mode citations for your query.

From the FetchSERP response, you can extract citation URLs from the AI Overview or AI Mode section.

Step 7 — Display & Compare

Visualize the overlap (or gap) between your simulated retrieval results and live AI search output.

Step 8 — Run the Full Workflow

Execute the complete pipeline from extraction to comparison in one automated run.
