# Workout Widget - Complete Color Map

## All Colors Used in Workout Widget

### 1. CollapsibleSection Headers
**Location**: Exercise headers, Muscle Groups section, Sets section
- **Background (normal)**: `#F0F0F0` (light grey)
- **Background (hover)**: `#E0E0E0` (darker grey)
- **Border**: `#CCCCCC` (light grey)
- **Toggle Icon Color**: `#666666` (medium grey)
- **Header Label**: Default (black, bold, 11pt)

### 2. QSpinBox (Reps, Duration)
**Location**: Set rows (Reps field), Workout Information (Duration field)
- **Background**: `white`
- **Text Color**: `#333333` (dark grey)
- **Border**: `#CCCCCC` (light grey)
- **Up/Down Buttons (normal)**: `#F0F0F0` (light grey)
- **Up/Down Buttons (hover)**: `#E0E0E0` (darker grey)
- **Dropdown Menu Background**: `#E0E0E0` (darker grey) - **CURRENT ISSUE HERE**
- **Dropdown Menu Text**: `#333333` (dark grey)
- **Dropdown Selected Item**: `#C0C0C0` (medium grey) with `#000000` (black) text

### 3. QDoubleSpinBox (Weight)
**Location**: Set rows (Weight field)
- **Background**: `white`
- **Text Color**: `#333333` (dark grey)
- **Border**: `#CCCCCC` (light grey)
- **Up/Down Buttons (normal)**: `#F0F0F0` (light grey)
- **Up/Down Buttons (hover)**: `#E0E0E0` (darker grey)
- **Dropdown Menu Background**: `#E0E0E0` (darker grey) - **CURRENT ISSUE HERE**
- **Dropdown Menu Text**: `#333333` (dark grey)
- **Dropdown Selected Item**: `#C0C0C0` (medium grey) with `#000000` (black) text

### 4. QLineEdit (Comment, Exercise Name)
**Location**: Set rows (Comment field), Exercise headers (Exercise Name field)
- **Background**: `white`
- **Text Color**: `#333333` (dark grey)
- **Border**: `#CCCCCC` (light grey)
- **Invalid Border**: `red` (2px solid)

### 5. QTextEdit (Workout Notes)
**Location**: Workout Information section
- **Background**: `white`
- **Text Color**: `#333333` (dark grey)
- **Border**: `#CCCCCC` (light grey)

### 6. QCheckBox (Muscle Groups)
**Location**: Workout Information section, Exercise Muscle Groups section
- **Default styling** (no custom stylesheet applied)
- **Text**: Default (black)

### 7. QPushButton
**Location**: Various buttons throughout
- **Default styling** (no custom stylesheet, except Save button has bold font)
- **Remove Exercise**: Default
- **Add Set**: Default
- **Add Exercise**: Default
- **Clear Workout**: Default
- **Save Workout**: Bold font

### 8. QLabel
**Location**: Various labels
- **Volume Label**: Bold, 12pt (default black)
- **Other labels**: Default (black)

## ISSUE IDENTIFIED

The problem is that **QSpinBox and QDoubleSpinBox don't use QMenu for their dropdowns**. They use a different popup mechanism. The actual dropdown that appears when you:
- Right-click on the spinbox
- Use mouse wheel
- Click and drag
- Use keyboard navigation

This popup is styled using `QAbstractSpinBox` or system-level styling, not QMenu.

## SOLUTION NEEDED

We need to style the actual spinbox popup using:
- `QAbstractSpinBox` pseudo-states
- Or apply stylesheet at the application level
- Or use a different approach for the popup styling
