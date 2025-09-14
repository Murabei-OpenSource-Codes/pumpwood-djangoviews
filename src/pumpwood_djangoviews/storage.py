"""Storage end-point to download files."""
from urllib.parse import urljoin
from django.core.files.storage import Storage
from pumpwood_djangoauth.config import storage_object, MEDIA_URL


class PumpwoodStorage(Storage):
    """Stotage to integrate Pumpwood Auth and Storage with Django APIs."""

    def _save(self, name, content) -> str:
        """Save file using pumpwood storage object defined at django auth.

        It will use enviroment variable to set the object.

        Args:
            name (str):
                Full name of the file.
            content:
                File content.

        Returns:
            Final name of the file at storage location.
        """
        saved_file_name = storage_object.write_file(
            file_path="", file_name=name,
            data=content.read(), if_exists='fail',
            safe_filename=False)
        return saved_file_name

    def exists(self, name: str) -> bool:
        """Check if file exists at the Storage.

        It will use enviroment variable to set the object.

        Args:
            name (str):
                Full name of the file.

        Returns:
            True if file already exists.
        """
        return storage_object.check_file_exists(name)

    def url(self, name: str) -> str:
        """Return a URL that will be used to retrieve file.

        It use the media path set as url with Pumpwood Auth which is an
        authenticated end-point. File will be server as streaming directly
        from storage.

        Args:
            name (str):
                Full name of the file.

        Returns:
            Return the absolute path of the file.
        """
        # Check if media path was set as absolute
        temp_MEDIA_URL = MEDIA_URL
        if temp_MEDIA_URL[0] != "/":
            temp_MEDIA_URL = "/" + temp_MEDIA_URL
        return urljoin(temp_MEDIA_URL, name)
