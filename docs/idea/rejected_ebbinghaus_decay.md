# Architecture Decision: Rejection of Ebbinghaus Forgetting Curve Logic

## Status
**Rejected**

## Context
In the pursuit of optimizing the `Ripen`'s knowledge retention, a proposal was made to replace the existing simple Garbage Collection (GC) mechanism (which archives knowledge unaccessed for 180 days) with a complex, biologically-inspired memory decay model based on the **Ebbinghaus Forgetting Curve**. 

The proposed formula would calculate retrievability ($R$) based on:
$R = I \times \exp(-\frac{D \times t}{S})$
(Where $I$ = Importance, $t$ = Time since last access, $S$ = Stability, $D$ = Decay Rate).

## Decision
We explicitly decided **NOT** to implement this logic and to retain the simple Time-To-Live (TTL) based garbage collection. This falls under the principle of **YAGNI (You Aren't Gonna Need It)**.

## Rationale

A simulated review by domain experts highlighted several critical flaws in the proposal:

1. **Performance & Architectural Bottlenecks (Database Architect Perspective)**
   SQLite lacks built-in advanced mathematical functions like `exp()`. Implementing this logic would require fetching tens of thousands of metadata rows into Python memory, performing the calculations, and writing the results back during every GC cycle. This would completely undermine the I/O optimizations recently achieved through FTS5 integration.
   
2. **Category Error in Agentic Memory (AI/RAG Engineer Perspective)**
   The Ebbinghaus curve and Spaced Repetition systems are designed for human cognitive learning (memorizing vocabulary, etc.). AI agent context windows do not function this way. What matters for an LLM is **Semantic Relevance** (achieved via Vector Embeddings) and **Keyword Match/Freshness** (achieved via BM25/FTS5). Simulating human forgetting does not inherently improve retrieval accuracy for LLMs.

3. **Loss of Predictability & Accountability (UX/PM Perspective)**
   A system governed by complex, multi-variable exponential decay becomes a "black box". If a user or operator asks, "Why was this critical piece of architecture forgotten by the agent?", it is much easier to explain and troubleshoot "It wasn't accessed for 180 days" rather than tracing back a compounded stability and decay score over time. Predictability is paramount in developer tools.

4. **Maintenance Overhead (Software Engineering Perspective)**
   The current simple TTL approach satisfies 95% of the practical requirements for managing stale data. The remaining 5% does not justify the massive increase in code complexity, potential bugs, and background processing overhead.

## Conclusion
The system remains in a highly optimized and stable state. We will continue to rely on the robust combination of **Hybrid Search (Vector + FTS5 BM25)** for retrieval ranking and **Simple TTL (180 days)** for storage cleanup.
