-- Summit Supply Co. — sample sales & workforce database (SQLite)
--
-- Five tables, designed so real questions need multi-table reasoning:
--
--   Employees ◄──┐ ManagerID (self-reference: org chart)
--      ▲   ▲    │
--      │   └────┘
--      │ AccountManagerID            EmployeeID (sales rep who handled the order)
--   Customers ◄──── Orders ────────────────────────────► Employees
--                     │
--                     ▼
--                 OrderItems ────► Products
--
-- Conventions: dates are ISO-8601 TEXT ('YYYY-MM-DD'); money is USD;
-- state columns hold 2-letter USPS codes ('CA'); booleans are INTEGER 0/1.

PRAGMA foreign_keys = ON;

CREATE TABLE Employees (
    EmployeeID      INTEGER PRIMARY KEY,
    FirstName       TEXT    NOT NULL,
    LastName        TEXT    NOT NULL,
    Email           TEXT    NOT NULL UNIQUE,
    JobTitle        TEXT    NOT NULL,
    Department      TEXT    NOT NULL,
    ManagerID       INTEGER REFERENCES Employees (EmployeeID),
    HireDate        TEXT    NOT NULL,
    TerminationDate TEXT,
    Salary          REAL    NOT NULL CHECK (Salary > 0),
    EmploymentType  TEXT    NOT NULL CHECK (EmploymentType IN ('Full-Time', 'Part-Time', 'Contract')),
    Status          TEXT    NOT NULL CHECK (Status IN ('Active', 'On Leave', 'Terminated')),
    City            TEXT    NOT NULL,
    State           TEXT    NOT NULL,
    CHECK (TerminationDate IS NULL OR TerminationDate > HireDate),
    CHECK ((Status = 'Terminated') = (TerminationDate IS NOT NULL))
);

CREATE TABLE Customers (
    CustomerID       INTEGER PRIMARY KEY,
    FirstName        TEXT    NOT NULL,
    LastName         TEXT    NOT NULL,
    CompanyName      TEXT,
    Email            TEXT    NOT NULL UNIQUE,
    Phone            TEXT,
    City             TEXT    NOT NULL,
    State            TEXT    NOT NULL,
    PostalCode       TEXT    NOT NULL,
    Segment          TEXT    NOT NULL CHECK (Segment IN ('Consumer', 'Small Business', 'Corporate')),
    LoyaltyTier      TEXT    NOT NULL CHECK (LoyaltyTier IN ('Bronze', 'Silver', 'Gold', 'Platinum')),
    SignupDate       TEXT    NOT NULL,
    AccountManagerID INTEGER REFERENCES Employees (EmployeeID)
);

CREATE TABLE Products (
    ProductID      INTEGER PRIMARY KEY,
    ProductName    TEXT    NOT NULL,
    SKU            TEXT    NOT NULL UNIQUE,
    Category       TEXT    NOT NULL,
    Brand          TEXT    NOT NULL,
    UnitPrice      REAL    NOT NULL CHECK (UnitPrice > 0),
    UnitCost       REAL    NOT NULL CHECK (UnitCost > 0),
    StockQuantity  INTEGER NOT NULL CHECK (StockQuantity >= 0),
    ReorderLevel   INTEGER NOT NULL CHECK (ReorderLevel >= 0),
    IsDiscontinued INTEGER NOT NULL DEFAULT 0 CHECK (IsDiscontinued IN (0, 1)),
    LaunchDate     TEXT    NOT NULL
);

CREATE TABLE Orders (
    OrderID       INTEGER PRIMARY KEY,
    CustomerID    INTEGER NOT NULL REFERENCES Customers (CustomerID),
    EmployeeID    INTEGER REFERENCES Employees (EmployeeID),
    OrderDate     TEXT    NOT NULL,
    Status        TEXT    NOT NULL CHECK (Status IN ('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled', 'Returned')),
    Channel       TEXT    NOT NULL CHECK (Channel IN ('Online', 'Phone', 'In-Store', 'Partner')),
    PaymentMethod TEXT    NOT NULL CHECK (PaymentMethod IN ('Credit Card', 'PayPal', 'Bank Transfer', 'Gift Card', 'Digital Wallet')),
    PaymentStatus TEXT    NOT NULL CHECK (PaymentStatus IN ('Paid', 'Pending', 'Refunded', 'Voided')),
    ShippingCost  REAL    NOT NULL DEFAULT 0 CHECK (ShippingCost >= 0),
    ShippedDate   TEXT,
    DeliveredDate TEXT,
    ShipCity      TEXT    NOT NULL,
    ShipState     TEXT    NOT NULL,
    CHECK (ShippedDate IS NULL OR ShippedDate >= OrderDate),
    CHECK (DeliveredDate IS NULL OR DeliveredDate >= ShippedDate)
);

CREATE TABLE OrderItems (
    OrderItemID INTEGER PRIMARY KEY,
    OrderID     INTEGER NOT NULL REFERENCES Orders (OrderID),
    ProductID   INTEGER NOT NULL REFERENCES Products (ProductID),
    Quantity    INTEGER NOT NULL CHECK (Quantity > 0),
    UnitPrice   REAL    NOT NULL CHECK (UnitPrice > 0),
    Discount    REAL    NOT NULL DEFAULT 0 CHECK (Discount >= 0 AND Discount <= 0.3),
    UNIQUE (OrderID, ProductID)
);

-- Indexes on the hot join / range paths. Deliberately NOT indexed:
-- Customers.State, Orders.Status, Products.Category, Employees.HireDate —
-- so the optimizer can make realistic index recommendations.
CREATE INDEX idx_orders_customer    ON Orders (CustomerID);
CREATE INDEX idx_orders_orderdate   ON Orders (OrderDate);
CREATE INDEX idx_orders_employee    ON Orders (EmployeeID);
CREATE INDEX idx_orderitems_order   ON OrderItems (OrderID);
CREATE INDEX idx_orderitems_product ON OrderItems (ProductID);
CREATE INDEX idx_employees_manager  ON Employees (ManagerID);
