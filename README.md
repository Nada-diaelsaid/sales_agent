# Observability
is a general software concept that refers to having complete visibility into every layer of your application.
In the context of LLM applications, that's often tracking things like the prompt, the response, token usage, and then any calls that happen around the calls that you're making to LLMs.
Observability is typically made up of traces and spans.
Traces refer to full run through of your application, so a single trace would be one and end run of your application from an input all the way through to an output.
And then traces are comprised of multiple spans. Spans are individual steps of calls to LLMs or code, or lookups to databases or whatever might be.
So one trace is made of multiple spans, and they're typically presented in this hierarchical way where spans can be nested underneath each other to show that they're operating within another span.
And then a set of spans will make up one trace hierarchy. Spans are typically presented in this hierarchical manner here where you have individual spans that are nested within each other, all making up one trace.
And you might have spans for LLM calls as you see in the image here. You might have spans for tools. You might have chain spans which are just general logic steps that happen within a trace.

Traces and spans come from a framework called OpenTelemetry.

**Why is observability important?**
1) It simplifies debugging, rather than throwing print statements all over.
2) Provides a detailed log of each call made to the app, which is necessary to run/monitor performance evaluation.
3) Helps you understand and eventually control the unpredictable behaviors of LLMs.

**To run Phoenix server**
In CLI run: phoenix serve 
It should run on localhost:6006