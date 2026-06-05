from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StarRatingWidget(QWidget):
    """
    Interactive 5-star rating widget for priority selection.
    Clicking a star sets the priority to that value (1-5).
    """
    
    ratingChanged = pyqtSignal(int)  # Signal emitted when rating changes
    
    def __init__(self, parent=None) -> None:
        """
        Initialize Star Rating Widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.rating = 3  # Default to 3 stars
        self.hover_rating = 0  # Track hover state
        self.star_labels: list[QLabel] = []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Create 5 clickable star labels
        for i in range(1, 6):
            star = QLabel("★")
            star.setStyleSheet("font-size: 20pt; color: #CCCCCC; cursor: pointer;")
            star.setAlignment(Qt.AlignmentFlag.AlignCenter)
            star.setMinimumSize(24, 24)
            
            # Store index for click handling
            star.star_index = i
            
            # Enable mouse tracking for hover
            star.setMouseTracking(True)
            
            # Connect mouse events
            star.mousePressEvent = lambda event, idx=i: self._on_star_clicked(idx)
            star.enterEvent = lambda event, idx=i: self._on_star_hover(idx)
            star.leaveEvent = lambda event: self._on_star_leave()
            
            self.star_labels.append(star)
            layout.addWidget(star)
        
        self._update_stars()
    
    def _on_star_clicked(self, rating: int) -> None:
        """
        Set rating when star is clicked.
        
        Args:
            rating: Rating value (1-5)
        """
        self.rating = rating
        self.hover_rating = 0  # Clear hover state
        self._update_stars()
        self.ratingChanged.emit(rating)
    
    def _on_star_hover(self, rating: int) -> None:
        """
        Handle hover over star.
        
        Args:
            rating: Rating value being hovered (1-5)
        """
        self.hover_rating = rating
        self._update_stars()
    
    def _on_star_leave(self) -> None:
        """Handle mouse leaving star area."""
        self.hover_rating = 0
        self._update_stars()
    
    def _update_stars(self) -> None:
        """Update star display based on current rating and hover state."""
        # Use hover_rating if active, otherwise use rating
        display_rating = self.hover_rating if self.hover_rating > 0 else self.rating
        
        for i, star in enumerate(self.star_labels, 1):
            if i <= display_rating:
                star.setText("★")  # Filled star
                # Slightly brighter on hover
                if self.hover_rating > 0:
                    star.setStyleSheet("font-size: 20pt; color: #FFD700; cursor: pointer;")
                else:
                    star.setStyleSheet("font-size: 20pt; color: #FFD700; cursor: pointer;")
            else:
                star.setText("☆")  # Empty star
                star.setStyleSheet("font-size: 20pt; color: #CCCCCC; cursor: pointer;")
    
    def get_rating(self) -> int:
        """
        Get current rating value.
        
        Returns:
            Current rating (1-5)
        """
        return self.rating
    
    def set_rating(self, rating: int) -> None:
        """
        Set rating value programmatically.
        
        Args:
            rating: Rating value (1-5), will be clamped to valid range
        """
        self.rating = max(1, min(5, rating))  # Clamp to 1-5
        self.hover_rating = 0  # Clear hover state
        self._update_stars()
