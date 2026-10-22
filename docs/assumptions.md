# Assumptions

**1. What counts as "in scope".**
I treated anything about this database or about SQL as in scope. That includes questions like "what does the
Segment column mean?" or "what's the difference between WHERE and HAVING?". Everything else gets the refusal
message from the brief, word for word. Requests to delete or change data are about the database, so they get a
different reply: the agent explains that it only reads data and offers a SELECT that shows the affected rows.

**2. Dates.**
"After January 2024" means from 1 January 2024 onward, the same way the brief's example reads it. Relative
periods such as "last 90 days" or "this year" are measured from the date the sample data ends (20 October 2026),
not from today. That way the same question always gives the same answer.

**3. Business terms.**
"Revenue" or "sales" means net revenue: quantity × the price actually charged × (1 − discount), leaving out
cancelled and returned orders and shipping costs. "Customers from California" means where the customer lives,
which the database stores as the state code `CA`.

**4. Follow-ups and unclear requests.**
A follow-up like "only those from California" changes the previous query instead of starting a new one. If a
request is ambiguous or names something the database doesn't have, the agent asks one short question rather than
guessing. A wrong query that runs is worse than a quick question.

**5. The sample database.**
The brief didn't come with a schema, so I designed a small retail company database: 5 tables (employees,
customers, products, orders, order lines), filled with realistic generated data, in SQLite. Every query runs
read-only. The PostgreSQL and MySQL versions shown with each answer are translations and are not executed.
