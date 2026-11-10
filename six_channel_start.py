"""Single entry point for the six-channel desktop publisher."""
from publisher_start import start
from publisher_profiles import initial_profile
import run


if __name__ == '__main__':
    previous = initial_profile()
    start(config_path=previous if previous != run.ROOT / 'config.json'
          else run.ROOT / 'profiles' / 'english.json')
