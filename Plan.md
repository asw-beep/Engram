# PROJECT PROPOSAL

# ENGRAM
## Enterprise Engineering Knowledge Intelligence Platform

**Project Category:** Artificial Intelligence · Retrieval-Augmented Generation · Backend Engineering · Distributed Systems

**Proposed Architecture:** Multi-tenant, permission-aware RAG platform

**Technology Stack:** Python, FastAPI, Next.js, PostgreSQL, Qdrant, OpenSearch, Redis, Celery, Docker, AWS

**Project Duration:** 8 Weeks (Proposed)

**Project Status:** Proposed

---

# 1. Executive Summary

Modern software engineering organisations generate and maintain enormous amounts of technical knowledge throughout their development and operational lifecycles. This knowledge is distributed across source code repositories, technical documentation, architecture specifications, API references, incident reports, engineering discussions, and operational runbooks.

Although these resources contain valuable information, accessing and connecting them efficiently remains a significant challenge. Engineers frequently spend considerable time searching through multiple repositories and documentation systems to understand existing implementations, investigate production incidents, identify architectural decisions, and evaluate the impact of proposed changes.

Traditional keyword-based search systems are often insufficient for answering contextual and multi-document questions. Conventional conversational AI systems also have limitations because they may lack access to organisation-specific information, generate unsupported answers, and fail to enforce document-level access restrictions.

**Engram** proposes an Enterprise Engineering Knowledge Intelligence Platform powered by Retrieval-Augmented Generation (RAG).

The platform will ingest, process, index, and retrieve engineering knowledge from multiple sources. It will combine semantic vector search with traditional keyword retrieval, reranking, metadata filtering, and large language models to generate contextual answers supported by verifiable source citations.

Unlike a conventional document-question-answering application, Engram will be designed around enterprise requirements such as multi-tenancy, access control, incremental data synchronization, source versioning, fault tolerance, observability, and retrieval evaluation.

The project aims to demonstrate how modern AI retrieval systems can be engineered into reliable, scalable, and maintainable software platforms.

# 2. Problem Statement

## 2.1 Background

Software organisations maintain technical knowledge across several independent systems.

Typical sources include:

- GitHub and GitLab repositories.
- Architecture design documents.
- Architecture Decision Records (ADRs).
- Technical design specifications.
- API documentation and OpenAPI specifications.
- Production incident reports and postmortems.
- Deployment and troubleshooting runbooks.
- Developer onboarding documentation.
- Engineering guidelines and internal knowledge articles.

These resources are generally maintained by different teams and evolve independently.

As organisations grow, the amount of technical knowledge increases, making it increasingly difficult to identify the right information and establish relationships between different pieces of knowledge.

## 2.2 Existing Challenges

**1. Fragmented engineering knowledge**

Technical information is distributed across repositories, documents, and development platforms. Engineers must manually navigate multiple systems to gather the information required to solve a problem.

**2. Limited contextual search**

Traditional search engines primarily depend on keyword matching. They may fail to retrieve relevant information when users describe a technical concept differently from the terminology used in the original documentation.

**3. Lack of cross-document understanding**

Understanding a software system frequently requires combining information from multiple sources.

For example, investigating an authentication failure may require examining the API gateway implementation, authentication middleware, architecture documentation, and historical incident reports.

Conventional search systems do not naturally synthesise this information.

**4. Loss of architectural knowledge**

Important engineering decisions are frequently documented in historical discussions, design proposals, and ADRs. Engineers joining a project later may struggle to understand why particular architectural decisions were made.

**5. Unreliable AI-generated answers**

Generic LLM applications can generate plausible but unsupported answers when they lack sufficient context. This is particularly problematic when engineers rely on AI-generated explanations for debugging or architectural decisions.

**6. Security and access-control limitations**

Enterprise engineering documentation may contain sensitive information. A knowledge system must ensure that users can retrieve only information they are authorised to access.

## 2.3 Proposed Solution

Engram will provide a unified engineering knowledge interface that allows engineers to query information across multiple technical sources using natural language.

The system will:

1. Connect to supported engineering knowledge sources.
2. Extract and normalise technical information.
3. Divide content into meaningful, searchable units.
4. Generate semantic embeddings and maintain keyword indexes.
5. Retrieve relevant information using hybrid search.
6. Rerank retrieved passages according to relevance.
7. Generate grounded answers using an LLM.
8. Provide citations linking answers to original sources.
9. Enforce user permissions throughout the retrieval process.
10. Continuously synchronize the knowledge base as source content changes.

The objective is to transform fragmented engineering documentation into a unified, searchable, and continuously updated knowledge system.

# 3. Project Objectives

The primary objective is to design and implement a production-oriented RAG knowledge engine for software engineering organisations.

The specific objectives are:

1. Develop a modular ingestion framework supporting multiple engineering knowledge sources.
2. Implement structure-aware document parsing and intelligent chunking.
3. Build a hybrid retrieval system combining dense vector search and sparse keyword search.
4. Integrate reciprocal rank fusion and cross-encoder reranking.
5. Implement contextual answer generation using retrieved evidence.
6. Provide source-level citations and traceability.
7. Design a multi-tenant architecture with permission-aware retrieval.
8. Support incremental ingestion, document versioning, and deletion propagation.
9. Develop asynchronous processing and retry mechanisms for reliable ingestion.
10. Establish an evaluation framework to measure retrieval quality, answer quality, latency, and reliability.
11. Deploy the application using containerised infrastructure.
12. Implement observability for monitoring system performance and operational health.

# 4. Scope of the Project

## 4.1 Core Functional Scope

The initial implementation will support the following capabilities.

### A. Knowledge Source Integration

The platform will support ingestion from:

- GitHub repositories.
- PDF documents.
- Markdown files.
- DOCX documents.
- OpenAPI specifications.
- Architecture Decision Records.
- Technical design documents.

GitHub integration will allow users to connect repositories and synchronize their technical content.

### B. Document Processing

The ingestion engine will perform:

- File identification and format detection.
- Content extraction.
- Markdown and code parsing.
- Metadata extraction.
- Document normalization.
- Structure-aware chunking.
- Content hashing.
- Duplicate detection.
- Embedding generation.

### C. Intelligent Knowledge Retrieval

The retrieval engine will support:

- Semantic vector search.
- BM25 keyword retrieval.
- Metadata-based filtering.
- Reciprocal Rank Fusion.
- Cross-encoder reranking.
- Context selection and deduplication.

### D. Contextual Question Answering

Users will be able to ask questions about their engineering knowledge base.

The system will:

- Understand user queries.
- Retrieve relevant evidence.
- Generate contextual answers.
- Include source citations.
- Identify insufficient evidence.
- Avoid presenting unsupported claims as facts.

### E. Enterprise Management

The platform will provide:

- User authentication.
- Organisation and tenant management.
- Role-based access control.
- Document-level permissions.
- Repository management.
- Ingestion job monitoring.
- Query history.
- Audit logging.

## 4.2 Out of Scope for Initial Release

The following capabilities are considered future extensions:

- Autonomous code modification.
- Automated production deployment.
- Fully autonomous debugging agents.
- Real-time collaboration.
- Extensive knowledge graph reasoning.
- Automatic architectural refactoring.
- Integration with every enterprise SaaS platform.

These features will not be prioritised until the foundational retrieval and security architecture is validated.

# 5. Proposed System Architecture

## 5.1 Architectural Overview

Engram will use a modular architecture consisting of an application layer, ingestion pipeline, retrieval pipeline, storage layer, and observability infrastructure.

The architecture will initially follow a modular monolith approach, with independently scalable background workers.

This approach reduces deployment complexity while maintaining clear boundaries between system components.

### Major Architectural Components

**1. Frontend Application**

Technology: Next.js and TypeScript.

Responsibilities:

- User authentication interface.
- Organisation workspace.
- Knowledge source management.
- Document ingestion status.
- Conversational search interface.
- Citation visualization.
- Query history.
- Administrative dashboard.

**2. API and Application Layer**

Technology: Python and FastAPI.

Responsibilities:

- API request handling.
- Authentication and authorization.
- Tenant identification.
- Query orchestration.
- Ingestion job creation.
- Knowledge source management.
- Rate limiting.
- Request validation.

**3. Ingestion Service**

Responsibilities:

- Source synchronization.
- File extraction.
- Content normalization.
- Metadata enrichment.
- Chunk generation.
- Embedding generation.
- Search index updates.

**4. Retrieval Service**

Responsibilities:

- Query preprocessing.
- Query rewriting.
- Dense retrieval.
- Sparse retrieval.
- Result fusion.
- Reranking.
- Context assembly.

**5. Generation Service**

Responsibilities:

- Prompt construction.
- Context-aware answer generation.
- Citation generation.
- Evidence validation.
- Response formatting.

**6. Storage Layer**

The system will use separate storage technologies for different data requirements.

- PostgreSQL: Canonical metadata, users, tenants, permissions, and document records.
- Qdrant: Dense vector embeddings and semantic retrieval.
- OpenSearch: Keyword-based retrieval and BM25 search.
- Redis: Caching and background job coordination.
- S3 or MinIO: Original documents and processed artifacts.

**7. Background Processing Infrastructure**

Technology: Celery and Redis.

Responsibilities:

- Asynchronous ingestion.
- Embedding generation.
- Index updates.
- Retry handling.
- Scheduled synchronization.
- Long-running document processing.

**8. Observability Infrastructure**

Technology: OpenTelemetry, Prometheus, and Grafana.

Responsibilities:

- Request tracing.
- API latency monitoring.
- Retrieval performance monitoring.
- Worker health monitoring.
- Token consumption tracking.
- Error and failure analysis.

## 5.2 High-Level Data Flow

The system will contain two major execution paths.

### A. Knowledge Ingestion Flow

1. An administrator connects a knowledge source.
2. The backend validates the source and establishes access credentials.
3. A background ingestion job is created.
4. The connector fetches source content.
5. The parser extracts and normalizes the content.
6. Metadata and access-control information are attached.
7. Content is divided into meaningful chunks.
8. Embeddings are generated.
9. Document metadata is stored in PostgreSQL.
10. Embeddings are indexed in Qdrant.
11. Searchable text is indexed in OpenSearch.
12. The ingestion job is marked successful.

The pipeline must support incremental processing so that unchanged content is not unnecessarily reprocessed.

### B. Question Answering Flow

1. A user submits a natural-language question.
2. The backend authenticates the user.
3. The system resolves the user's tenant and access permissions.
4. The query is analysed and optionally rewritten.
5. Dense and sparse retrieval execute in parallel.
6. Results are combined using Reciprocal Rank Fusion.
7. Candidate passages are reranked.
8. Relevant passages are filtered and assembled into context.
9. The LLM generates an answer using the retrieved evidence.
10. Citations are validated.
11. The response is returned with source references.

The system must not generate a confident answer when sufficient supporting evidence cannot be retrieved.

# 6. Detailed Technical Design

## 6.1 Document Ingestion and Parsing

The ingestion system will be designed using a connector-based architecture.

Each connector will implement a common interface for fetching documents and their metadata.

Supported initial connectors:

- GitHub connector.
- Local file upload connector.
- Document parsing connector.

The GitHub connector will retrieve repository information and supported files through the GitHub API.

Each document will contain metadata such as:

- Document ID.
- Tenant ID.
- Source ID.
- Repository name.
- File path.
- File type.
- Commit SHA or revision identifier.
- Last modified timestamp.
- Content hash.
- Access-control metadata.

A content hash will help identify unchanged documents and prevent redundant processing.

## 6.2 Intelligent Chunking

Chunking is a critical component because retrieval quality depends heavily on how source content is segmented.

Simple fixed-size chunking can split important technical information across boundaries.

Engram will initially use structure-aware chunking.

Examples:

- Markdown: Split using headings and subheadings.
- Code: Split using classes, functions, and logical blocks.
- API specifications: Split using endpoints and operation definitions.
- ADRs: Preserve decision context, alternatives, and consequences.
- Incident reports: Preserve incident description, timeline, root cause, and remediation.

Each chunk will retain its parent document metadata and source location.

Future improvements may include semantic chunking and parent-child retrieval.

## 6.3 Embedding Generation

The initial embedding model will be BGE-M3.

Embeddings will represent the semantic meaning of engineering passages.

The generated vectors will be stored in Qdrant.

The embedding pipeline will support:

- Batch processing.
- Embedding caching.
- Retry handling.
- Model version tracking.
- Re-embedding when models change.

Embedding model selection will be evaluated against the project's actual engineering retrieval dataset rather than assumed to be optimal.

## 6.4 Hybrid Retrieval

Engram will use a hybrid retrieval architecture.

Dense retrieval identifies semantically related passages, even when the user's wording differs from the original documentation.

Sparse retrieval uses BM25 to identify exact technical terms, identifiers, symbols, error codes, and API paths.

The two retrieval methods complement each other.

Example:

A user searches:

"Where do we validate the JWT signing key?"

Dense retrieval may identify authentication design documentation.

Sparse retrieval may identify source code containing `JWT_SECRET` or `verify_signature`.

Combining both retrieval methods increases the likelihood of retrieving useful evidence.

## 6.5 Reciprocal Rank Fusion

The system will combine dense and sparse retrieval rankings using Reciprocal Rank Fusion.

The RRF score is calculated as:

RRF(d) = Σ 1 / (k + rank_i(d))

Where:

- d represents a retrieved document or passage.
- rank_i(d) is its rank in retrieval system i.
- k is a constant used to reduce the influence of high-ranking positions.

This produces a unified ranking without requiring the raw similarity scores of different retrieval systems to be directly comparable.

## 6.6 Reranking

After hybrid retrieval, the system will rerank the candidate passages using a cross-encoder.

The initial proposed model is BGE-reranker-v2-m3.

Unlike bi-encoder retrieval, a cross-encoder evaluates a query and candidate passage together.

This enables more detailed relevance assessment.

The pipeline will:

1. Retrieve an initial candidate set.
2. Combine candidates using RRF.
3. Remove duplicates.
4. Apply cross-encoder reranking.
5. Select the highest-relevance passages.
6. Assemble the final context.

## 6.7 Context Assembly

Retrieved passages will be processed before being passed to the LLM.

The context assembly component will perform:

- Duplicate removal.
- Relevance thresholding.
- Source diversity consideration.
- Token-budget management.
- Metadata preservation.
- Permission revalidation.

The objective is to provide sufficient evidence without exceeding the model's context limits or introducing irrelevant information.

## 6.8 Answer Generation and Citations

The generation component will receive:

- Original user question.
- Retrieved evidence.
- Source metadata.
- Instructions for grounded answer generation.

The model will be instructed to answer using the supplied evidence and explicitly acknowledge uncertainty.

Each citation should reference:

- Original document.
- Repository or source.
- File path or document section.
- Relevant line or page range, where available.
- Document revision.

Citation validation will ensure that references resolve to actual retrieved evidence.

The system will distinguish between retrieved evidence and model-generated interpretation.

# 7. Enterprise Security and Reliability

Security will be treated as a fundamental architectural requirement rather than a feature added at the end.

## 7.1 Multi-Tenancy

The system will support multiple organisations using the same platform.

Every tenant-owned record will contain tenant identification.

Database queries, vector searches, keyword searches, and cached results will enforce tenant boundaries.

Tenant isolation will be tested through adversarial access scenarios.

## 7.2 Authentication and Authorization

Authentication will use a standards-based identity integration, initially OIDC.

Authorization will use role-based access control and document-level permissions.

Proposed roles:

- Organisation Administrator.
- Knowledge Base Administrator.
- Engineer.
- Viewer.

Document access may additionally depend on repository or source-level permissions.

The system must preserve source permissions when indexing external content.

## 7.3 Data Security

Security measures will include:

- HTTPS communication.
- Secure credential storage.
- Encryption at rest.
- Environment-based secret management.
- Input validation.
- Rate limiting.
- Audit logging.
- Prompt injection defenses.
- Permission-aware caching.

Retrieved content will be treated as untrusted data. Instructions contained within indexed documents must never override the system's security policies.

## 7.4 Fault Tolerance

The ingestion system will implement:

- Idempotent job execution.
- Configurable retries.
- Exponential backoff.
- Dead-letter handling.
- Processing checkpoints.
- Job status tracking.
- Duplicate detection.

The indexing pipeline must account for partial failures across PostgreSQL, Qdrant, and OpenSearch.

PostgreSQL will act as the canonical metadata store, while search indexes will be treated as rebuildable projections.

Document updates and deletions must eventually propagate consistently across all indexes.

# 8. Database Design

The initial relational data model will contain the following entities.

| Entity | Responsibility |
|---|---|
| Tenants | Organisation information |
| Users | User identity and account information |
| Memberships | User-to-tenant relationships and roles |
| Sources | Connected knowledge sources |
| Documents | Canonical document metadata |
| Document Versions | Historical document revisions |
| Chunks | Extracted and indexed content segments |
| ACL Grants | Access-control information |
| Ingestion Jobs | Processing status and execution history |
| Query Logs | Search and answer request metadata |
| Feedback | User feedback and answer evaluation |

Qdrant will maintain vector representations linked to chunk identifiers.

OpenSearch will maintain searchable textual representations.

The database design will account for indexing, tenant-scoped queries, referential integrity, and document lifecycle management.

# 9. Technology Stack and Justification

| Component | Proposed Technology | Justification |
|---|---|---|
| Frontend | Next.js, TypeScript | Modern interactive application |
| Backend | Python, FastAPI | Asynchronous API development and AI ecosystem |
| Relational DB | PostgreSQL | Reliable structured data storage |
| Vector DB | Qdrant | Semantic vector retrieval |
| Search Engine | OpenSearch | BM25 and keyword search |
| Cache | Redis | Caching and job coordination |
| Workers | Celery | Asynchronous task execution |
| Object Storage | AWS S3 / MinIO | Document and artifact storage |
| Embeddings | BGE-M3 | Multilingual and multi-function embedding model |
| Reranking | BGE-reranker-v2-m3 | Cross-encoder relevance scoring |
| LLM | Provider-agnostic API | Flexible model integration |
| Containers | Docker | Reproducible deployment |
| Cloud | AWS | Production deployment infrastructure |
| Monitoring | Prometheus and Grafana | Operational metrics and dashboards |
| Tracing | OpenTelemetry | Distributed request tracing |
| CI/CD | GitHub Actions | Automated testing and deployment |

The initial implementation will avoid unnecessary technology proliferation. Components will be introduced only when they provide measurable architectural benefits.

# 10. Testing and Evaluation Methodology

A major objective of this project is to demonstrate that the retrieval system performs reliably.

The evaluation framework will measure retrieval quality, answer quality, security, and operational performance.

## 10.1 Retrieval Evaluation

The following metrics will be used:

**Recall@K**

Measures whether relevant passages appear among the top K retrieved results.

**Mean Reciprocal Rank (MRR)**

Measures how highly the first relevant result appears.

**Normalized Discounted Cumulative Gain (NDCG)**

Measures the quality of the complete ranked retrieval list, considering graded relevance.

## 10.2 Generation Evaluation

The following dimensions will be evaluated:

- Answer relevance.
- Faithfulness to retrieved evidence.
- Citation correctness.
- Completeness.
- Appropriate uncertainty handling.

Automated evaluation will be supplemented by manual inspection of representative questions.

## 10.3 Performance Evaluation

The system will be tested for:

- End-to-end query latency.
- Retrieval latency.
- Embedding generation latency.
- Ingestion throughput.
- API response time.
- Worker processing time.
- Memory and CPU utilisation.

## 10.4 Security Evaluation

Security testing will cover:

- Cross-tenant data isolation.
- Unauthorised document retrieval.
- Permission changes.
- Deleted document propagation.
- Cache isolation.
- Prompt injection attempts.
- Malicious document content.

## 10.5 Proposed Acceptance Criteria

| Metric | Initial Target |
|---|---:|
| Recall@5 | ≥ 85% |
| Citation validity | ≥ 99% |
| Query latency | p95 below 5 seconds |
| Tenant isolation | 100% adversarial test pass |
| Ingestion recovery | Successful recovery from all tested transient failures |

These values are proposed engineering targets, not existing benchmark results. They will be validated against a documented evaluation dataset and workload.

# 11. Implementation Methodology

The project will follow an incremental development methodology.

## Phase 1: Foundation and Basic RAG

**Duration: Weeks 1–2**

Activities:

- Establish project repository.
- Design initial database schema.
- Implement FastAPI backend.
- Implement document upload and GitHub ingestion.
- Develop document parsing and normalization.
- Implement initial chunking strategy.
- Integrate embedding generation.
- Configure Qdrant.
- Develop basic retrieval and answer generation.

Deliverable: A working document ingestion and question-answering application.

## Phase 2: Advanced Retrieval

**Duration: Weeks 3–4**

Activities:

- Integrate OpenSearch.
- Implement BM25 retrieval.
- Implement hybrid retrieval.
- Add Reciprocal Rank Fusion.
- Integrate cross-encoder reranking.
- Implement query preprocessing.
- Develop context assembly.
- Implement citation validation.
- Create retrieval evaluation datasets.

Deliverable: An advanced retrieval engine with measurable retrieval performance.

## Phase 3: Enterprise Features

**Duration: Weeks 5–6**

Activities:

- Implement authentication.
- Introduce tenant management.
- Implement role-based and document-level access control.
- Develop asynchronous ingestion workers.
- Implement incremental synchronization.
- Add document versioning.
- Implement deletion propagation.
- Add retry mechanisms and audit logging.

Deliverable: A multi-tenant knowledge platform with enterprise security and reliability features.

## Phase 4: Deployment and Optimisation

**Duration: Weeks 7–8**

Activities:

- Containerise application components.
- Configure deployment infrastructure.
- Implement CI/CD workflows.
- Integrate observability.
- Perform load testing.
- Measure retrieval and generation latency.
- Evaluate failure recovery.
- Optimise resource consumption.
- Prepare technical documentation.

Deliverable: A deployed, benchmarked, and documented engineering knowledge platform.

# 12. Deployment Architecture

The initial deployment will use Docker containers.

Proposed deployment components:

- Next.js frontend container.
- FastAPI backend container.
- Celery worker containers.
- PostgreSQL database.
- Qdrant vector database.
- OpenSearch cluster or single-node deployment for the initial workload.
- Redis instance.
- S3-compatible object storage.
- Monitoring and tracing components.

AWS will be the proposed cloud environment.

The deployment architecture will initially prioritise cost efficiency and reproducibility.

As workload increases, the system can transition to independently managed infrastructure with managed database services, object storage, and independently scalable application components.

Kubernetes will remain an optional future deployment improvement rather than an initial requirement.

# 13. Expected Outcomes

Upon completion, the project is expected to deliver:

1. A functional enterprise engineering knowledge platform.
2. A modular multi-source ingestion framework.
3. A hybrid retrieval and reranking engine.
4. Citation-backed contextual answer generation.
5. A multi-tenant application with permission-aware retrieval.
6. An incremental synchronization mechanism.
7. A fault-tolerant background processing pipeline.
8. An evaluation framework with reproducible benchmarks.
9. A deployed application with monitoring and observability.
10. Comprehensive technical documentation and architecture diagrams.

The project will demonstrate practical understanding of modern RAG architectures, search systems, backend engineering, database design, distributed processing, application security, and cloud deployment.

# 14. Future Enhancements

Once the core system is stable, several advanced capabilities can be explored.

## 14.1 Engineering Knowledge Graph

Introduce a graph representation of engineering entities such as:

- Services.
- APIs.
- Databases.
- Repositories.
- Architecture decisions.
- Incidents.
- Dependencies.

This will enable relationship-based queries and multi-hop retrieval.

Example:

"What services could be affected if the authentication service changes its token validation logic?"

## 14.2 Code-Aware Retrieval

Develop specialised code retrieval using:

- Abstract Syntax Trees.
- Symbol extraction.
- Function and class relationships.
- Import dependency analysis.
- Code-aware chunking.

This would improve retrieval for questions involving specific implementations.

## 14.3 Impact Analysis

Combine repository metadata, dependency relationships, architecture documents, and historical incidents to provide evidence-backed change-impact analysis.

## 14.4 Advanced Query Planning

Introduce query decomposition for complex questions requiring evidence from multiple sources.

For example:

"Compare our original payment architecture with the current implementation and explain why the migration was necessary."

The system could break this into smaller retrieval tasks and synthesise the results.

## 14.5 Feedback-Driven Retrieval Optimisation

Use user feedback and evaluation results to identify retrieval weaknesses and improve:

- Chunking strategies.
- Embedding models.
- Search weights.
- Reranking.
- Context selection.

# 15. Risks and Mitigation Strategies

| Risk | Mitigation |
|---|---|
| Poor retrieval quality | Benchmark chunking, embeddings, hybrid search and reranking |
| High LLM costs | Caching, token budgets and model selection |
| Slow query execution | Parallel retrieval, indexing and performance monitoring |
| Stale information | Webhooks, scheduled sync and version tracking |
| Permission leakage | Pre-retrieval filtering, tenant isolation and adversarial tests |
| Ingestion failures | Retryable jobs, checkpoints and idempotency |
| Hallucinated answers | Evidence-grounded generation and citation validation |
| Complex infrastructure | Modular monolith and incremental component introduction |
| Prompt injection | Treat retrieved content as untrusted and enforce policy outside the LLM |

# 16. Project Deliverables

The final submission will contain:

**Software Deliverables**
- Fully functional web application.
- Backend API.
- Ingestion and retrieval pipelines.
- Database schema and migrations.
- Docker deployment configuration.
- Automated test suite.

**Engineering Documentation**
- Software Requirements Specification.
- High-level architecture document.
- Low-level design document.
- API documentation.
- Database ER diagram.
- Deployment guide.
- Security design document.

**Evaluation Deliverables**
- Benchmark dataset.
- Retrieval evaluation report.
- Performance benchmark report.
- Security test report.
- Cost analysis.
- Known limitations and future work.

**Demonstration**
- Live application.
- Sample engineering knowledge base.
- Cross-document question-answering demonstrations.
- Retrieval and evaluation dashboard.

# 17. Conclusion

Engram aims to address a meaningful problem in modern software engineering: the difficulty of accessing, connecting, and maintaining organisational technical knowledge.

By combining intelligent document ingestion, hybrid retrieval, reranking, contextual answer generation, and enterprise security controls, the project will demonstrate a practical application of Retrieval-Augmented Generation beyond basic conversational interfaces.

The emphasis will be on engineering a complete system rather than simply integrating an LLM with a vector database.

Particular attention will be given to retrieval quality, data consistency, access control, fault tolerance, observability, and reproducible evaluation.

The resulting platform will serve as a practical demonstration of how AI capabilities can be integrated into production-oriented software systems.

---

# Appendix A: Initial Project Success Criteria

The project will be considered ready for its first complete demonstration when:

- [ ] Users can create and manage an organisation workspace.
- [ ] Users can connect a GitHub repository.
- [ ] The system can ingest supported engineering documents.
- [ ] Documents are parsed, chunked, and indexed.
- [ ] Semantic and keyword retrieval work together.
- [ ] Reranking improves or demonstrably changes retrieval quality.
- [ ] Answers contain validated source citations.
- [ ] Unsupported questions are handled appropriately.
- [ ] User permissions are enforced across retrieval systems.
- [ ] Document updates and deletions propagate correctly.
- [ ] Background jobs recover from tested transient failures.
- [ ] Retrieval and generation metrics are recorded.
- [ ] Automated tests cover critical security boundaries.
- [ ] The application is deployable using documented instructions.

# Appendix B: Recommended Initial Engineering Dataset

For the initial proof of concept, the knowledge base will use public and synthetic engineering resources.

Recommended sources:

1. Kubernetes GitHub repository and official documentation.
2. Apache Airflow GitHub repository and official documentation.
3. Public OpenAPI specifications.
4. Public software architecture and design documents.
5. Synthetic architecture decision records.
6. Synthetic production incident reports.
7. Synthetic engineering runbooks.

Synthetic documents will be explicitly labelled and will be used to simulate internal organisational knowledge without introducing confidential information.

# Appendix C: Architectural Design Principle

**Build a reliable retrieval system before building an autonomous AI system.**

The primary focus of the first implementation will be deterministic ingestion, accurate retrieval, permission enforcement, evidence-grounded generation, and measurable system performance.

Advanced capabilities such as knowledge graphs, autonomous agents, and impact analysis will be introduced only after the foundational architecture has been validated.

This principle will help keep the project technically focused, achievable, and defensible during engineering interviews.